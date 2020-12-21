import logging
import threading
import time

import xbmc

from .const import VAR_PLAYER_SPEED

logger = logging.getLogger(__name__)

MAX_UNDERSHOOT = 0.25
"""Amount of tolerance in seconds for waking up early.

If the listener wakes up and the difference to the checkpoint is bigger than this value, 
it goes back to sleep for the remaining time.
"""

MAX_OVERSHOOT = 1.5
"""Max seconds allowed to move past the start of a checkpoint before ignoring it."""

MAX_SEEK_AGE = 3
"""Amount of time in seconds after a seek before the seek time expires.

In other words, this is the time after which the Kodi player should start reporting accurate values for 
`Player.getTime()` again.
"""


class PlayerCheckpointListener(xbmc.Player):
    """
    Aims to provide a simple interface for working with "checkpoints".
    A checkpoint is a time in a piece of media at which an action should be performed.
    This takes care the complexities of waiting for the player to reach a certain time and once reached,
    calls the `_reached_checkpoint` callback.

    Handles pausing, seeking, and playback speed changes.
    """

    def __init__(self, *args, **kwargs):
        super(PlayerCheckpointListener, self).__init__(*args, **kwargs)
        self._playback_speed = 1.0

        self.__seek = None  # type: Optional[Tuple[float, float]]
        self.__wakeup = threading.Condition()
        self.__wakeup_triggered = False

        self._thread = None  # Optional[threading.Thread]
        self._stop = False

    @property
    def _seek_time(self):  # type: () -> Optional[float]
        try:
            seek_time, timestamp = self.__seek
        except TypeError:
            return None

        age = time.time() - timestamp
        if age > MAX_SEEK_AGE:
            logger.debug("seek time expired")
            self.__seek = None
            return None

        logger.debug("estimating time based on recent seek")
        return seek_time + age * self._playback_speed

    @_seek_time.setter
    def _seek_time(self, value):  # type: (float) -> None
        if value is None:
            self.__seek = None
        else:
            self.__seek = (value, time.time())

    def _get_current_time(self):  # type:() -> float
        """Get the current time of the current item.

        This method is the same as `Player.getTime` unless it is called just after seeking.
        For a period after seeking `Player.getTime` still reports the time prior to seeking.
        This is problematic for us because we rely on the current time being correct.
        This function solves this by returning the seek time instead, until the seek time is cleared again.

        If `Player.getTime` raises an exception, this function returns 0.0.

        Returns:
            Current time in seconds.
        """
        seek_time = self._seek_time
        if seek_time is None:
            try:
                return self.getTime()
            except RuntimeError:
                logger.exception("failed to get playback time, assuming 0.0")
                return 0.0

        return seek_time

    def __sleep_until(self, target_time):  # type: (float) -> bool
        logger.debug("waiting until %s (or until woken)", target_time)
        while not (self.__wakeup_triggered or self._stop):
            wait_for = (target_time - self._get_current_time()) / self._playback_speed
            if wait_for <= MAX_UNDERSHOOT:
                return True

            with self.__wakeup:
                logger.debug("sleeping for %s second(s) (or until woken)", wait_for)
                self.__wakeup.wait(wait_for)

        return False

    def __idle(self):  # type: () -> bool
        if self.__wakeup_triggered or self._stop:
            return False

        cp = self._get_checkpoint()
        if cp is not None and self._playback_speed > 0:
            return self.__sleep_until(cp)

        logger.debug("sleeping until wakeup triggered")
        with self.__wakeup:
            self.__wakeup.wait()

        # wakeup must have been triggered
        return False

    def __t_cp_reached(self):
        cp = self._get_checkpoint()
        if cp is None:
            logger.warning("reached checkpoint but there's no checkpoint")
            self._select_next_checkpoint()
            return

        overshoot = self._get_current_time() - cp
        if overshoot > MAX_OVERSHOOT:
            logger.warning(
                "overshot checkpoint %s by %s second(s), ignoring", cp, overshoot
            )
            self._select_next_checkpoint()
            return

        try:
            self._reached_checkpoint()
        except Exception:
            logger.exception("something went wrong at checkpoint: %s", cp)

        self._reset_next_checkpoint()

    def __t_event_loop(self):
        self._playback_speed = float(xbmc.getInfoLabel(VAR_PLAYER_SPEED))

        self._stop = False
        self._seek_time = None
        self.__wakeup_triggered = False

        while not self._stop:
            cp_reached = self.__idle()
            self.__wakeup_triggered = False
            if self._stop:
                logger.debug("woke up: stopping")
                break

            if cp_reached:
                logger.debug("woke up: reached checkpoint")
                self.__t_cp_reached()
            else:
                logger.debug("woke up: state changed")
                self._select_next_checkpoint()

    @property
    def _thread_running(self):  # type: () -> bool
        t = self._thread
        return t is not None and t.is_alive()

    def _trigger_wakeup(self):
        if not self._thread_running:
            return

        logger.debug("triggering wakeup")
        with self.__wakeup:
            self.__wakeup_triggered = True
            self.__wakeup.notify_all()

    def start(self):  # type: () -> None
        if self._thread_running:
            if self._stop:
                logger.debug("waiting for previous checkpoint listener to stop")
                self._thread.join()
            else:
                logger.warning("checkpoint listener already running, stopping")
                self.stop()

        if self.isPlaying():
            logger.info("starting checkpoint listener")
        else:
            logger.warning(
                "starting checkpoint listener but player isn't playing anything"
            )

        self._thread = threading.Thread(
            target=self.__t_event_loop, name="Checkpoint Listener"
        )
        self._thread.start()

    def stop(self):
        if not self._thread_running:
            return

        logger.debug("stopping checkpoint listener")
        self._stop = True
        self._trigger_wakeup()

        logger.debug("waiting for listener to join")
        self._thread.join()

        logger.debug("listener stopped")

    def onPlayBackSeek(self, target, offset):  # type: (int, int) -> None
        self._seek_time = target / 1000.0
        self._trigger_wakeup()

    def onPlayBackEnded(self):  # type: () -> None
        self.stop()

    def onPlayBackError(self):  # type: () -> None
        self.stop()

    def onPlayBackStopped(self):  # type: () -> None
        self.stop()

    def onPlayBackPaused(self):  # type: () -> None
        self._seek_time = None
        self._trigger_wakeup()

    def onPlayBackResumed(self):  # type: () -> None
        self._trigger_wakeup()

    def onPlayBackSpeedChanged(self, speed):  # type: (int) -> None
        self._seek_time = None
        self._playback_speed = float(speed)
        self._trigger_wakeup()

    def _select_next_checkpoint(self):  # type: () -> None
        """Select the next checkpoint.

        Choose the next checkpoint strictly AFTER the current time.
        You should use `_get_current_time` instead of `getTime` to get the current time.
        """
        raise NotImplementedError

    def _reset_next_checkpoint(self):  # type: () -> None
        """Reset the next checkpoint.

        After calling this method `_get_next_checkpoint` MUST return `None`.

        This is called AFTER `_reached_checkpoint`.
        """
        raise NotImplementedError

    def _get_checkpoint(self):  # type: () -> Optional[float]
        """Get the current checkpoint.

        This function should be computationally cheap.
        The return value of this function MUST only change when `_select_next_checkpoint` is called.
        The only exception is `_reset_next_checkpoint`.

        Returns:
            Time in seconds of the next checkpoint. `None` if there is no checkpoint.
        """
        raise NotImplementedError

    def _reached_checkpoint(self):  # type: () -> None
        """Called when a checkpoint is reached.

        This is called when the checkpoint returned by `_get_checkpoint` is reached.
        """
        raise NotImplementedError
