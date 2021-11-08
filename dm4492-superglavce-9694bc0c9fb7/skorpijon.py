#!/usr/bin/env python3
from ev3dev.ev3 import LargeMotor, MediumMotor, Sound
import pycurl
import ujson
import sys
import math
from io import BytesIO
from time import time, sleep
from enum import Enum
from collections import deque

ROBOT_ID = 0
SERVER_IP = "192.168.0.168" #spremeni na njihovega
GAME_STATE_FILE = "game.json" #spremeni na game.json

MOTOR_LEFT_PORT = 'outB'
MOTOR_RIGHT_PORT = 'outC'
MOTOR_CLAW_PORT = 'outD'
ROBOT_WIDTH = 230
ROBOT_LENGTH = 190

SPEED_MAX = 900
SPEED_BASE_MAX = 800

# Parametri za PID
PID_TURN_KP = 3.0
PID_TURN_KI = 0.5
PID_TURN_KD = 0.0
PID_TURN_INT_MAX = 100
PID_STRAIGHT_KP = 2.0
PID_STRAIGHT_KI = 0.5
PID_STRAIGHT_KD = 0.01
PID_STRAIGHT_INT_MAX = 100

class State(Enum):
    def __str__(self):
        return str(self.name)
    IDLE = 0
    ROTATE_TO_APPLE = 1
    TO_APPLE = 2
    ROTATE_TO_HOME = 3
    BRINGING_HOME = 4
    BRINGING_TO_OP = 5
    MESSING_OP = 6
    CLEARING = 7 #sploh rabmo???

class Connection():
    def __init__(self, url: str):
        self._url = url
        self._buffer = BytesIO()
        self._pycurlObj = pycurl.Curl()
        self._pycurlObj.setopt(self._pycurlObj.URL, self._url)
        self._pycurlObj.setopt(self._pycurlObj.CONNECTTIMEOUT, 10)
        self._pycurlObj.setopt(self._pycurlObj.WRITEDATA, self._buffer)

    def request(self, debug=False):
        self._buffer.seek(0, 0)
        self._buffer.truncate()
        self._pycurlObj.perform()
        msg = self._buffer.getvalue().decode()
        try:
            return ujson.loads(msg)
        except ValueError as err:
            if debug:
                print('Napaka pri razclenjevanju datoteke JSON: ' + str(err))
                print('Sporocilo streznika:')
                print(msg)
            return -1
    def test_delay(self, num_iters: int = 10):
        sum_time = 0
        for i in range(num_iters):
            start_time = time()
            if self.request() == -1:
                robot_die()
            elapsed_time = time() - start_time
            sum_time += elapsed_time
        return sum_time / num_iters

class PID():
    def __init__(self, setpoint: float, Kp: float, Ki: float = None, Kd: float = None, integral_limit: float = None):
        self._setpoint = setpoint
        self._Kp = Kp
        self._Ki = Ki
        self._Kd = Kd
        self._integral_limit = integral_limit
        self._error = None
        self._time = None
        self._integral = None
        self._value = None

    def reset(self, setpoint: float, Kp: float, Ki: float = None, Kd: float = None, integral_limit: float = None):
        if setpoint is not None:
            self._setpoint = setpoint
        if Kp is not None:
            self._Kp = Kp
        if Ki is not None:
            self._Ki = Ki
        if Kd is not None:
            self._Kd = Kd
        if integral_limit is not None:
            self._integral_limit = integral_limit
        self._error = None
        self._time = None
        self._integral = None
        self._value = None

    def update(self, measurement: float) -> float:
        if self._value is None:
            self._value = measurement
            self._time = time()
            self._integral = 0
            self._error = self._setpoint - measurement
            return self._Kp * self._error
        else:
            time_now = time()
            delta_time = time_now - self._time
            self._time = time_now
            self._value = measurement
            error = self._setpoint - self._value

            P = self._Kp * error

            if self._Ki is None:
                I = 0
            else:
                self._integral += error * delta_time
                I = self._Ki * self._integral
                if self._integral_limit is not None:
                    I = max(min(I, self._integral_limit), (-1)*(self._integral_limit))
            
            if self._Kd is None:
                D = 0
            else:
                D = self._Kd * (error - self._error) / delta_time

            self._error = error
            return P + I + D

class Point():
    def __init__(self, position):
        self.x = position[0]
        self.y = position[1]

    def __str__(self):
        return '('+str(self.x)+', '+str(self.y)+')'

def get_angle(p1: Point, a1: float, p2: Point) -> float:
    a = math.degrees(math.atan2(p2.y-p1.y, p2.x - p1.x))
    a_rel = a - a1
    if abs(a_rel) > 180:
        if a_rel > 0:
            a_rel -= 360
        else:
            a_rel += 360
    return a_rel

def get_distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2.x-p1.x)**2 + (p2.y-p1.y)**2)


def init_large_motor(port: str) -> LargeMotor:
    motor = LargeMotor(port)
    return motor

def init_medium_motor(port: str) -> MediumMotor:
    motor = MediumMotor(port)
    return motor

def take():
    motor_claw.run_forever(speed_sp = 750)

def leave():
    motor_claw.run_forever(speed_sp = -750)

def closest_home() -> Point:
    if team_my_tag == 'team1':
        top = Point(basket_my['topRight'][0:2])
        bottom = Point(basket_my['bottomRight'][0:2])
    else:
        top = Point(basket_my['topLeft'][0:2])
        bottom = Point(basket_my['bottomLeft'][0:2])
    
    return Point([top.x, (top.y+bottom.y)/2])

def robot_die():
    motor_left.stop(stop_action='brake')
    motor_right.stop(stop_action='brake')
    Sound.play_song((
        ('D4', 'e'),
        ('C4', 'e'),
        ('A3', 'h')))
    sys.exit(0)

#------------------------------------------------------------------------------
#                                    PROGRAM
#------------------------------------------------------------------------------
#nastavitev motorjev
print('Setting motors...', end = '')
motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)
motor_claw = init_medium_motor(MOTOR_CLAW_PORT)
motor_claw.stop_action = 'brake'
print('OK')

#povezava s streznikom
url = SERVER_IP+'/'+GAME_STATE_FILE
print('Connecting to ' + url + ' ... ', end='')
conn = Connection(url)
print('OK')
print('Delay to server... ', end='', flush=True)
print('%.4f s' % (conn.test_delay(num_iters=10)))

#preveri, ce robot tekmuje
game_state = conn.request()
if ROBOT_ID == game_state['team1']['id']:
    team_my_tag = 'team1'
    team_op_tag = 'team2'
elif ROBOT_ID == game_state['team2']['id']:
    team_my_tag = 'team2'
    team_op_tag = 'team1'
else:
    robot_die()
print('Robot is on ' + team_my_tag)

#dobi kosaro od ekipe
basket_my = game_state['field']['baskets'][team_my_tag]
basket_op = game_state['field']['baskets'][team_op_tag]

#Nastavi PID
PID_turn = PID(setpoint = 0, Kp = PID_TURN_KP, Ki = PID_TURN_KI, Kd = PID_TURN_KD, integral_limit = PID_TURN_INT_MAX)
PID_frwd_base = PID(setpoint = 0, Kp = PID_STRAIGHT_KP, Ki = PID_STRAIGHT_KI, Kd = PID_STRAIGHT_KD, integral_limit = PID_STRAIGHT_INT_MAX)
PID_frwd_turn = PID(setpoint = 0, Kp = PID_TURN_KP, Ki = PID_TURN_KI, Kd = PID_TURN_KD, integral_limit = PID_TURN_INT_MAX)

#Hitrost na obeh motorjih.
speed_right = 0
speed_left = 0

#nastavi seznam jabolk
taken_apples = []

#nastavi stanja
state = State.IDLE
state_old = State.IDLE
state_changed = False

targetList = []

while True:
    game_state = conn.request()
    if game_state != -1:
        game_on = game_state['gameOn']
        time_left = game_state['timeLeft']

        #nastavi pozicijo robota
        robot_pos = None
        robot_dir = None
        for robot_data in game_state['robots']:
            if robot_data['id'] == ROBOT_ID:
                robot_pos = Point(robot_data['position'][0:2])
                robot_dir = robot_data['direction']
        robot_alive = robot_pos is not None and robot_dir is not None

        #----------------------------------------------------------------------
        #                           glavna zanka
        #----------------------------------------------------------------------
        if robot_alive and game_on:
            if time_left < 30:
                break
            
            #------------------------------------------------------------------
            #                     izbere naslednjo tarco
            #------------------------------------------------------------------
            if state == State.IDLE:
                if state != state_old:
                    print('IDLE')
                state_old = State.IDLE
                #ustavi robota
                speed_left = 0
                speed_right = 0
                #nastavi vse tarce
                targets = game_state['apples']
                target_dist = 4000
                target_needed = 'appleGood'
                #izracuna pozicijo najblizjega dobrega jabolka
                for i in range(len(targets)):
                    if targets[i]['type'] == target_needed and targets[i]['id'] not in taken_apples:
                        dist = get_distance(robot_pos, Point(targets[i]['position'][0:2]))
                        if dist < target_dist:
                            target_dist = dist
                            target_pos = Point(position = targets[i]['position'][0:2])
                            target_id = targets[i]['id']
                target_dir = get_angle(robot_pos, robot_dir, target_pos)
                state = State.ROTATE_TO_APPLE
                print('Goint to apple: '+target_pos.__str__()) #naredi ce ni jabolk
                
            #------------------------------------------------------------------
            #                     rotira se do jabolka
            #------------------------------------------------------------------
            elif state == State.ROTATE_TO_APPLE:
                if state != state_old:
                    print('ROTATE TO APPLE')
                state_old = State.ROTATE_TO_APPLE
                
                targets = game_state['apples']
                for i in range(len(targets)):
                    if targets[i]['id'] == target_id:
                        target_pos = Point(position = targets[i]['position'][0:2])
                        break
                target_dir = get_angle(robot_pos, robot_dir, target_pos)

                print('Angle: '+str(target_dir))
                if abs(target_dir) > 5:
                    speed_left = -target_dir/5*10
                    speed_right = target_dir/5*10
                else:
                    speed_left = 0
                    speed_right = 0
                    state = State.TO_APPLE

            #------------------------------------------------------------------
            #                     vozi se do jabolka
            #------------------------------------------------------------------
            elif state == State.TO_APPLE:
                if state != state_old:
                    print('TO APPLE')
                state_old = State.TO_APPLE

                targets = game_state['apples']
                for i in range(len(targets)):
                    if targets[i]['id'] == target_id:
                        target_pos = Point(position = targets[i]['position'][0:2])
                        break
                target_dist = get_distance(robot_pos, target_pos)
                target_dir = get_angle(robot_pos, robot_dir, target_pos)

                print('Distance: '+str(target_dist))
                if target_dist < 120:
                    take()
                    sleep(0.5)
                    speed_left = 0
                    speed_right = 0
                    state = State.ROTATE_TO_HOME
                else:
                    u_turn = PID_frwd_turn.update(measurement = target_dir)
                    u_base = PID_frwd_base.update(measurement = target_dist)
                    u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                    speed_right = -u_base - u_turn
                    speed_left = -u_base + u_turn
            
            #------------------------------------------------------------------
            #                     rotira se do doma
            #------------------------------------------------------------------
            elif state == State.ROTATE_TO_HOME:
                if state != state_old:
                    print('ROTATE TO HOME')
                state_old = State.ROTATE_TO_HOME

                home_pos = closest_home()
                home_dir = get_angle(robot_pos, robot_dir, home_pos)

                print('Angle: '+str(home_dir))
                if abs(home_dir) > 5:
                    speed_left = -home_dir/5*15
                    speed_right = home_dir/5*15
                else:
                    speed_left = 0
                    speed_right = 0
                    state = State.BRINGING_HOME
            
            #------------------------------------------------------------------
            #                     jabolko pelje domov
            #------------------------------------------------------------------
            elif state == State.BRINGING_HOME:
                if state != state_old:
                    print('BRINGING HOME')
                state_old = State.BRINGING_HOME

                home_dist = get_distance(robot_pos, home_pos)
                home_dir = get_angle(robot_pos, robot_dir, home_pos)

                if home_dist < 50:
                    leave()
                    speed_left = 0
                    speed_right = 0
                    state = State.IDLE
                    taken_apples.append(target_id)
                else:
                    u_turn = PID_frwd_turn.update(measurement = home_dir)
                    u_base = PID_frwd_base.update(measurement = home_dist)
                    u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                    speed_right = -u_base - u_turn
                    speed_left = -u_base + u_turn

            
            #------------------------------------------------------------------
            #                   jabolko pelje nasprotniku
            #------------------------------------------------------------------
            elif state == State.BRINGING_TO_OP:
                #dodaj
                state = State.IDLE
                break

            #------------------------------------------------------------------
            #                     nagaja nasprotniku
            #------------------------------------------------------------------
            elif state == State.MESSING_OP:
                #dodaj
                break
            #robot se vozi
            speed_left = round(min(max(speed_left, -SPEED_MAX), SPEED_MAX))
            speed_right = round(min(max(speed_right, -SPEED_MAX), SPEED_MAX))
            motor_left.run_forever(speed_sp = speed_left)
            motor_right.run_forever(speed_sp = speed_right)

        else:
            motor_left.stop(stop_action = 'brake')
            motor_right.stop(stop_action = 'brake')
            motor_claw.stop(stop_action = 'brake')
            state = State.IDLE
