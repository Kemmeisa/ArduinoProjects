import argparse
import enum
import logging.config
import pathlib
import time

import pydantic
import RPi.GPIO as GPIO
import yaml


logger = logging.getLogger()


class SwitchPosition(enum.IntEnum):
    TURN = 0
    STRAIGHT = 1


class EventEdge(enum.IntEnum):
    FALLING = GPIO.FALLING
    RISING = GPIO.RISING
    BOTH = GPIO.BOTH


class L298NSwitchSettings(pydantic.BaseModel):
    initial_state: SwitchPosition = SwitchPosition.TURN
    debounce_ms: int = 200
    event_edge: EventEdge = EventEdge.RISING
    strobe_ms: int = 500
    name: str
    pin_enable: int
    pin_turn: int
    pin_straight: int
    pin_button: int

    @pydantic.field_validator('initial_state', mode='before')
    @classmethod
    def validate_switch_position(cls, value):
        try:
            return SwitchPosition[value]
        except KeyError as e:
            raise ValueError(
                f"Error validating switch position {e}. Valid switch positions are: {[p.name for p in SwitchPosition]}"
            )

    @pydantic.field_validator('event_edge', mode='before')
    @classmethod
    def validate_event_edge(cls, value):
        try:
            return EventEdge[value]
        except KeyError as e:
            raise ValueError(
                f"Error validating event edge {e}. Valid event edges are: {[v.name for v in EventEdge]}"
            )


class L298NSwitch:
    def __init__(self, cfg: L298NSwitchSettings):
        self.__state = None
        self.config = cfg
        self.state = self.config.initial_state

        self.__init_pins()
        self.__enable_button_interrupt()

    @property
    def state(self) -> SwitchPosition:
        return self.__state

    @state.setter
    def state(self, v: SwitchPosition) -> None:
        self.__state = v
        logger.debug(f'{self.config.name} -> {str(self.__state)}')

    def __set_direction_pins(self):
        GPIO.output(self.config.pin_turn, not self.state)
        GPIO.output(self.config.pin_straight, self.state)

    def __enable_switch(self):
        GPIO.output(self.config.pin_enable, True)

    def __disable_switch(self):
        GPIO.output(self.config.pin_enable, False)

    def __strobe(self):
        time.sleep(self.config.strobe_ms / 1000)

    def __init_pins(self):
        GPIO.setup(self.config.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.config.pin_enable, GPIO.OUT)
        GPIO.setup(self.config.pin_straight, GPIO.OUT)
        GPIO.setup(self.config.pin_turn, GPIO.OUT)

        self.__disable_switch()
        self.__set_direction_pins()

    def __enable_button_interrupt(self) -> None:
        GPIO.add_event_detect(
            self.config.pin_button,
            GPIO.RISING,
            callback=self.__toggle,
            bouncetime=self.config.debounce_ms
        )

    def __disable_button_interrupt(self) -> None:
        GPIO.remove_event_detect(self.config.pin_button)

    def __toggle(self, channel):
        self.__disable_button_interrupt()
        self.state ^= 1
        self.__enable_switch()
        self.__set_direction_pins()
        self.__strobe()
        self.__disable_switch()
        self.__enable_button_interrupt()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c',
        '--config',
        type=pathlib.Path,
        default='amherst_2005.yml',
        required=True,
        help='Scenario configuration file'
    )
    parser.add_argument(
        '-l',
        '--log-configuration',
        type=pathlib.Path,
        default='logging.yml',
        help='Python logging configuration file'
    )
    args = parser.parse_args()

    try:
        with open(args.log_configuration) as yml_file:
            logging.config.dictConfig(yaml.safe_load(yml_file))
            logger = logging.getLogger()
    except OSError as e:
        logger.error(e)

    logger.info(f"Using BCM ({GPIO.BCM}) pin configuration")
    GPIO.setmode(GPIO.BCM)

    try:
        with open(args.config) as yml_file:
            cfg_data = yaml.safe_load(yml_file)
    except OSError as e:
        logger.error(e)

    switches = list()
    for switch_cfg in cfg_data:
        print(switch_cfg)
        cfg = L298NSwitchSettings.model_validate(switch_cfg)
        switch = L298NSwitch(cfg=cfg)
        switches.append(switch)

    while True:
        time.sleep(1)



