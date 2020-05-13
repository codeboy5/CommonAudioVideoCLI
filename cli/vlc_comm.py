import socket
import sys
import subprocess
import time
import re
import json

from util import *

TITLE_REGEX = "Title=(.*)$"
DURATION_REGEX = "Duration=(.*)$"
SEEK_REGEX = "seek request to (.*)%$"
PAUSE_REGEX = "toggling resume$"
PLAY_REGEX = "toggling pause$"
START_REGEX = "pts: 0"
STOP_REGEX = "dead input"


class VLC_instance:
    def __init__(self, port, sub=None):
        self.sub = sub
        self.port = port
        self.proc = None

    @wait_until_error
    def readState(self):
        return json.loads(open('cache', 'r').read())

    def launch(self):
        bashCommand = 'vlc --extraintf rc --rc-host localhost:%d -vv' % (
            self.port)
        if(self.sub is not None):
            bashCommand += " --sub-file %s" % (self.sub)
        self.proc = subprocess.Popen(bashCommand.split(
        ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = ('localhost', self.port)
        wait_until_error(self.sock.connect, timeout=2)(self.server_address)
        self.sock.recv(1024)

    def play(self):
        message = 'play\n'.encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def pause(self):
        message = 'pause\n'.encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def seek(self, position):
        message = f"seek {position}\n".encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def enqueue(self, filePath):
        message = f"enqueue {filePath}\n".encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def faster_playback(self):
        message = 'faster\n'.encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def slower_playback(self):
        message = 'slower\n'.encode()
        send_until_writable()(self.sock.sendall, self.sock, message)

    def update(self):
        parse_logs(self)


    def getState(self):
        player = self
        state = player.readState()
        if state is None:
            return
        if('last_updated' in state.keys()):
            initial_pos = state['position']
            extra = time.perf_counter() - \
                float(state['last_updated']) if state['is_playing'] else 0
            final_pos = initial_pos + extra
            state['position'] = final_pos
            state.pop('last_updated')
            return state
        

def play_handler():
    print("Play signal recieved")


def parse_logs(player):
    for line in iter(player.proc.stdout.readline, ""):
            state = player.readState()
            if(state is None):
                state = {}
            if(re.search(TITLE_REGEX, line) is not None):
                state['title'] = re.search(TITLE_REGEX, line).groups()[0]
            elif('duration' not in state.keys() and re.search(DURATION_REGEX, line) is not None):
                state['duration'] = re.search(DURATION_REGEX, line).groups()[0]
            elif(re.search(START_REGEX, line) is not None):
                state['position'] = 0.0
                state['is_playing'] = True
                state['last_updated'] = time.perf_counter()
            elif(re.search(STOP_REGEX, line) is not None):
                state['is_playing'] = False
                state['position'] = 0.0
                state['last_updated'] = time.perf_counter()
            elif(re.search(PLAY_REGEX, line) is not None):
                state['is_playing'] = True
                state['last_updated'] = time.perf_counter()
            elif(re.search(PAUSE_REGEX, line) is not None):
                state['is_playing'] = False
                state['position'] = player.getState()['position'] if player.getState() is not None else 0
                state['last_updated'] = time.perf_counter()
            elif(re.search(SEEK_REGEX, line) is not None):
                match = re.search(SEEK_REGEX, line).groups()[0]
                if ('i_pos' in match):
                    match = match.split('=')[1].strip()
                state['position'] = float(match)*float(state['duration'])/100000.0
                state['last_updated'] = time.perf_counter()
            
            open('cache', 'w').write(json.dumps(state))
