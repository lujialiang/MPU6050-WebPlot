#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2013 KuoE0 <kuoe0.tw@gmail.com>
#
# Distributed under terms of the MIT license.
# ASCII art generated by http://patorjk.com/software/taag and use Big font.

"""

"""
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.websocket
import numpy as np
import serial
import signal
import ctypes
import sys
import json
import os

tornado_port = 8888

################################################################################
###            _____ _                 _____        __ _                     ###
###           / ____| |               |  __ \      / _(_)                    ###
###          | |    | | __ _ ___ ___  | |  | | ___| |_ _ _ __   ___          ###
###          | |    | |/ _` / __/ __| | |  | |/ _ \  _| | '_ \ / _ \         ###
###          | |____| | (_| \__ \__ \ | |__| |  __/ | | | | | |  __/         ###
###           \_____|_|\__,_|___/___/ |_____/ \___|_| |_|_| |_|\___|         ###
################################################################################

class signal_desc:
    def __init__(self, p_size, p_name):
        self.size = p_size
        self.name = p_name
    def __str__(self):
        return 'Name: {0}\tSize: {1} byte(s)'.format(self.name, self.size)
    def __repr__(self):
        return "<signal_desc name: {0} size: {1}>".format(self.name, self.size)

################################################################################
###                      _    _ _   _ _ _ _   _                              ###
###                     | |  | | | (_) (_) | (_)                             ###
###                     | |  | | |_ _| |_| |_ _  ___  ___                    ###
###                     | |  | | __| | | | __| |/ _ \/ __|                   ###
###                     | |__| | |_| | | | |_| |  __/\__ \                   ###
###                      \____/ \__|_|_|_|\__|_|\___||___/                   ###
################################################################################

def return_exception_msg(e):
    template = "An exception of type {0} occured. Arguments:\n{1!r}"
    message = template.format(type(e).__name__, e.args)
    return message


################################################################################
###    _____ _       _           _  __      __        _       _     _        ###
###   / ____| |     | |         | | \ \    / /       (_)     | |   | |       ###
###  | |  __| | ___ | |__   __ _| |  \ \  / /_ _ _ __ _  __ _| |__ | | ___   ###
###  | | |_ | |/ _ \| '_ \ / _` | |   \ \/ / _` | '__| |/ _` | '_ \| |/ _ \  ###
###  | |__| | | (_) | |_) | (_| | |    \  / (_| | |  | | (_| | |_) | |  __/  ###
###   \_____|_|\___/|_.__/ \__,_|_|     \/ \__,_|_|  |_|\__,_|_.__/|_|\___|  ###
################################################################################

# create serial object
serial_port = sys.argv[1]
serial_baudrate = int(sys.argv[2])
ser = serial.Serial(serial_port, serial_baudrate)

# read configuration from config file
with open('config.json') as f:
    config = json.load(f)

number_of_signal = len(config['signal_desc'])
signal_desc_list = list()

for s in sorted(config['signal_desc'], key=lambda x: x['order']):
    signal_desc_list.append(signal_desc(s['sizeof'], s['name']))

data_length = sum([s.size for s in signal_desc_list])
plot_size = config['plot_size']

callback_timeout = int(sys.argv[3])
client = list() # list of websocket client

serial_pending = list()
tx_status = False
size_window_MA = 0
signal_set = [[0] * number_of_signal] * plot_size
last_signal_set = [[0] * number_of_signal] * plot_size
signal_type = [s.name for s in signal_desc_list]

# SIGINT handler to close serial connection
def handler_SIGINT(signum, frame):
    global ser
    print "Signal {0} happened!".format(signum)
    print "Serial connection closed..."
    ser.close()
    sys.exit()

signal.signal(signal.SIGINT, handler_SIGINT)

# receive signal with a non-blocking way
def recieve_signal():

    try:
        if ser.inWaiting() != 0:
            data = ser.read(ser.inWaiting())
            parse_data(data)
    except Exception as e:
        print return_exception_msg(e)

# parse out the signal value
def parse_data(data):

    global signal_set

    if not hasattr(parse_data, 'unparse_data'):
        parse_data.unparse_data = ''

    parse_data.unparse_data += data
    used_to_parsed = parse_data.unparse_data

    # do not parse incomplete data
    valid = len(used_to_parsed) // data_length
    parse_data.unparse_data = used_to_parsed[data_length * valid:]
    used_to_parsed = used_to_parsed[:data_length * valid]

    if not used_to_parsed:
        return

    for i in xrange(valid):
        idx = i * data_length
        tmp = used_to_parsed[idx:idx + data_length]

        cnt = 0
        signal_group = list()
        for s in signal_desc_list:
            byte_data = [ord(b) for b in tmp[cnt:cnt + s.size]]
            value = reduce(lambda high, low: (high << 8) | low, byte_data)
            value = ctypes.c_int16(value).value
            cnt += s.size
            signal_group.append(value)

        signal_set.append(signal_group)

def moving_average_filter(last_signal, signal, size_window):
    
    signal = ([0] * ((size_window - 1) - len(last_signal))) + list(last_signal) + list(signal)
    return list(np.convolve(signal, [1.0 / size_window] * size_window, 'valid'))

def make_init_data():
    
    ret_signal = [[0] * 6] * plot_size
    ret_signal = zip(*ret_signal)

    ret = list()
    for label in signal_type:
        ret.append({ 'data': [p for p in enumerate([0] * plot_size)], 'label': label })
    ret = json.dumps({ 'signal': ret })

    return ret


def make_data():

    global signal_set
    global signal_type
    global last_signal_set
    global plot_size
    global size_window_MA

    # take out the signal to return
    signals = signal_set[:min(plot_size, len(signal_set))]
    last_signals = last_signal_set[-(min(size_window_MA - 1, len(last_signal_set))):]

    # fill the signal
    if len(signals) < plot_size:
        signals.extend([[0] * 6] * (plot_size - len(signals)))

    # transpose signals to make the signal of same type in same list
    signals = zip(*signals)
    last_signals = zip(*last_signals)

    ret = list()

    for i in xrange(6):
        if size_window_MA != 0:
            signals[i] = moving_average_filter(last_signals[i], signals[i], size_window_MA)
        ret.append({ 'data': [p for p in enumerate(signals[i])], 'label': signal_type[i] })
    ret = json.dumps({ 'signal': ret })
    return ret

# push signal data to client
def signal_tx():

    global tx_status
    global plot_size
    global signal_set
    global last_signal_set

    recieve_signal()

    if not tx_status:
        return
    
    # pop out the transmitted signal
    if len(signal_set):
        last_signal_set.append(signal_set.pop(0))
        last_signal_set = last_signal_set[-plot_size:]

    ret = make_data()
    for cl in client:
        cl.write_message(ret)


# tornado websocket handler
class socket_handler(tornado.websocket.WebSocketHandler):
    def open(self):
        client.append(self)
        self.write_message(make_init_data())

    def on_message(self, message):
        global tx_status
        global signal_set
        global toggle_moving_average_filter
        global size_window_MA

        token = message.split()

        if token[0] == "play":
            tx_status = True
        elif token[0] == "pause":
            tx_status = False
        elif token[0] == "clear":
            signal_set = [[0] * 6] * plot_size
            self.write_message(make_init_data())
        elif token[0] == "MAF":
            size_window_MA = int(token[1])
            self.write_message(make_data())

    def on_close(self):
        client.remove(self)

class homepage_handler(tornado.web.RequestHandler):
    def get(self):
        self.render('template/index.html')

settings = {
    'static_path': os.path.join(os.path.dirname(__file__), 'static'),
}

application = tornado.web.Application([
    (r'/', homepage_handler),
    (r'/ws', socket_handler),
    ], **settings)

if __name__ == "__main__":
    #tell tornado to run signal_tx every 1 ms
    serial_loop = tornado.ioloop.PeriodicCallback(signal_tx, callback_timeout)
    serial_loop.start()

    application.listen(tornado_port)
    print "Starting server on port number {0}...".format(tornado_port)
    print "Open at http://localhost:{0}/".format(tornado_port)

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        print 'Server closed...'
