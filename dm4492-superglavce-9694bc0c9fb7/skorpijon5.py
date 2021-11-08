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
SERVER_IP = "192.168.0.170" #spremeni na njihovega
GAME_STATE_FILE = "game.json"

MOTOR_LEFT_PORT = 'outB'
MOTOR_RIGHT_PORT = 'outC'
MOTOR_CLAW_PORT = 'outD'
ROBOT_WIDTH = 230
ROBOT_LENGTH = 190

SPEED_MAX = 900
SPEED_BASE_MAX = 800

# Parametri za PID
PID_TURN_KP = 3.0
PID_TURN_KI = 0.7
PID_TURN_KD = 0.08
PID_TURN_INT_MAX = 100
PID_STRAIGHT_KP = 1.7
PID_STRAIGHT_KI = 0.4 
PID_STRAIGHT_KD = 0.06
PID_STRAIGHT_INT_MAX = 100

class State(Enum):
    def __str__(self):
        return str(self.name)
    IDLE = 0
    ROTATE_TO_TARGET = 1
    TO_TARGET = 2
    OPENED = 3
    CLOSED = 4
    FOR_SHITS_AND_GIGGLES = 5

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

#vrne kot, relativen na robota
def get_angle(p1: Point, a1: float, p2: Point) -> float:
    a = math.degrees(math.atan2(p2.y-p1.y, p2.x - p1.x))
    a_rel = a - a1
    if abs(a_rel) > 180:
        if a_rel > 0:
            a_rel -= 360
        else:
            a_rel += 360
    return a_rel

#vrne razdaljo med dvema tockama
def get_distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2.x-p1.x)**2 + (p2.y-p1.y)**2)

#razvrsti jabolka na dobra in slaba
def return_good(apples):
    good = []
    for a in apples:
        if a['type'] == 'appleGood' and not in_my_basket(a) and not in_op_basket(a):
            good.append(a)
    return good

def return_bad(apples):
    bad = []
    for a in apples:
        if a['type'] == 'appleBad':
            bad.append(a)
    return bad

#pogleda, ce je jabolko v bazi
def in_my_basket(a):
    if a['position'][0] > basket_my['topLeft'][0] and a['position'][0] < basket_my['topRight'][0]:
        if a['position'][1] > basket_my['bottomLeft'][1] and a['position'][1] < basket_my['topLeft'][1]:
            return True
    return False
def in_op_basket(a):
    if a['position'][0] > basket_op['topLeft'][0] and a['position'][0] < basket_op['topRight'][0]:
        if a['position'][1] > basket_op['bottomLeft'][1] and a['position'][1] < basket_op['topLeft'][1]:
            return True
    return False

#nastavi velik motor
def init_large_motor(port: str) -> LargeMotor:
    motor = LargeMotor(port)
    return motor

#nastavi majhen motor
def init_medium_motor(port: str) -> MediumMotor:
    motor = MediumMotor(port)
    return motor

#zagrabi jabolko
def take():
    motor_claw.run_forever(speed_sp = 750)

#spusti jabolko
def leave():
    motor_claw.run_forever(speed_sp = -750)

#vrne najblizjo tocko kosare
def closest_home():
    top = Point(basket_my['topRight'][0:2])
    bottom = Point(basket_my['bottomLeft'][0:2])
    return {'position': [(top.x+bottom.x)/2, (top.y+bottom.y)/2], 'type': 'home', 'id': 200}
def closest_enemy():
    top = Point(basket_op['topRight'][0:2])
    bottom = Point(basket_op['bottomLeft'][0:2])
    return {'position': [(top.x+bottom.x)/2, (top.y+bottom.y)/2], 'type': 'enemy', 'id': 200}

#preveri, ce je kaj v napoto
def is_in_way(apples, pos, dir, target):
    for a in apples:
        if a['id'] is not target['id']:
            dist_accept = 400
            dire_accept = 15
            dist = get_distance(pos, Point(a['position'][0:2]))
            dire = get_angle(pos, dir, Point(a['position'][0:2]))
            if dist < dist_accept and abs(dire) < dire_accept:
                return True
    return False

#robot umre
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

print("--------------------------ZACETEK--------------------------")

#nastavitev motorjev
print('Nastavitev motorjev ... ', end = '')
motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)
motor_claw = init_medium_motor(MOTOR_CLAW_PORT)
motor_claw.stop_action = 'brake'
print('OK')

#povezava s streznikom
url = SERVER_IP+'/'+GAME_STATE_FILE
print('Povezujem na ' + url + ' ... ', end='')
conn = Connection(url)
print('OK')
print('Zakasnitev ... ', end='', flush=True)
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
print('Robot je na '+team_my_tag)

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
claw_state = State.OPENED

#naredi dva seznama, ki pokrijeta vsa jabolka
good_apples = []
bad_apples = []

#naredi strategijo
targetList = []
good_apples = return_good(game_state['apples'])
bad_apples = return_bad(game_state['apples'])

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
            #if time_left < 30:
                #break
            
            #------------------------------------------------------------------
            #                     izbere naslednjo tarco
            #------------------------------------------------------------------
            if state == State.IDLE:
                if state != state_old:
                    print("----------------------------IDLE---------------------------")
                    state_old = State.IDLE
                    leave()

                good_apples = return_good(game_state['apples'])
                bad_apples = return_bad(game_state['apples'])
                target = None
                
                if len(good_apples) > 0:
                    dist_max = 4000
                    for apple in good_apples:
                        dist = get_distance(robot_pos, Point(apple['position'][0:2]))
                        if dist < dist_max:
                            target = apple
                            dist_max = dist
                    targetList = [target]
                    state = State.ROTATE_TO_TARGET
                    print("Jabolko: "+str(target['id'])+", tip: dobro")                    
                elif len(bad_apples) > 0:
                    dist_max = 4000
                    for apple in bad_apples:
                        if in_my_basket(apple):
                            target = apple
                            break
                        dist = get_distance(robot_pos, Point(apple['position'][0:2]))
                        if dist < dist_max:
                            target = apple
                            dist_max = dist
                    targetList = [target]
                    state = State.ROTATE_TO_TARGET
                    print("Jabolko: "+str(target['id'])+", tip: slabo")
                else:
                    state = State.FOR_SHITS_AND_GIGGLES
                    print("Ni vec jabolk, gremo nagajat nasprotniku :-)")
                
            #------------------------------------------------------------------
            #                     rotira se do tarce
            #------------------------------------------------------------------
            elif state == State.ROTATE_TO_TARGET:
                if state != state_old:
                    print("----------------------ROTATE TO TARGET---------------------")
                    state_old = State.ROTATE_TO_TARGET

                target = targetList[0]
                target_dir = get_angle(robot_pos, robot_dir, Point(target['position'][0:2]))
                #print("Kot do tarce:"+str(target_dir))
                if abs(target_dir) > 5:
                    speed_left = -target_dir*2
                    speed_right = target_dir*2
                else:
                    speed_left = 0
                    speed_right = 0
                    state = State.TO_TARGET

            #------------------------------------------------------------------
            #                     vozi se do tarce
            #------------------------------------------------------------------
            elif state == State.TO_TARGET:
                if state != state_old:
                    print("--------------------------TO TARGET------------------------")
                    state_old = State.TO_TARGET

                target = targetList[0]
                found = 0
                targetID = target['id']

                if not (str(targetID) == '200'):
                    for i in game_state['apples']:
                        if targetID == i['id']:
                            target = i
                            found = True

                    if not found:
                        state = State.IDLE


                target_dist = get_distance(robot_pos, Point(target['position'][0:2]))
                target_dir = get_angle(robot_pos, robot_dir, Point(target['position'][0:2]))

                #target_dist = get_distance(robot_pos, Point(target['position'][0:2]))
                #target_dir = get_angle(robot_pos, robot_dir, Point(target['position'][0:2]))
                #print("Kot do tarce: "+str(target_dir)+", razdalja: "+str(target_dist))

                if str(target['id']) == '100': #waypoint
                    if target_dist < 50:
                        del targetList[0]
                        state = State.ROTATE_TO_TARGET
                    else:
                        u_turn = PID_frwd_turn.update(measurement = target_dir)
                        u_base = PID_frwd_base.update(measurement = target_dist)
                        u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                        speed_right = -u_base - u_turn
                        speed_left = -u_base + u_turn

                elif str(target['id']) == '200': #home
                    #target_dist = get_distance(robot_pos, Point(target['position'][0:2]))
                    if (target_dist) < 170:
                        targetList.clear()
                        leave()
                        speed_right = -700
                        speed_left = -700
                        motor_right.run_timed(time_sp = 1000, speed_sp = speed_right)
                        motor_left.run_timed(time_sp = 1000, speed_sp = speed_left)
                        motor_right.wait_while('running')
                        state = State.IDLE
                    else:
                        u_turn = PID_frwd_turn.update(measurement = target_dir)
                        u_base = PID_frwd_base.update(measurement = target_dist)
                        u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)  
                        speed_right = -u_base - u_turn
                        speed_left = -u_base + u_turn
                else:
                    if target_dist <= 120:
                        take()
                        targetList.clear()
                        if target['type'] == 'appleGood':
                            targetList.append(closest_home())
                            print("--------------------------GOING HOME-----------------------")
                        else:
                            targetList.append(closest_enemy())
                            print("---------------------------TO ENEMY------------------------")
                        state = State.ROTATE_TO_TARGET
                    else:
                        u_turn = PID_frwd_turn.update(measurement = target_dir)
                        u_base = PID_frwd_base.update(measurement = target_dist)
                        u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                        speed_right = -u_base - u_turn
                        speed_left = -u_base + u_turn
            
            #------------------------------------------------------------------
            #                     nagaja nasprotniku
            #------------------------------------------------------------------
            elif state == State.FOR_SHITS_AND_GIGGLES:
                if game_state['robots'][0]['id'] != ROBOT_ID:
                    target = game_state['robots'][0]
                else:
                    target = game_state['robots'][1]
                target_dist = get_distance(robot_pos, Point(target['position'][0:2]))
                target_dir = get_angle(robot_pos, robot_dir, Point(target['position'][0:2]))

                u_turn = PID_frwd_turn.update(measurement = target_dir)
                u_base = PID_frwd_base.update(measurement = target_dist)
                u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                speed_right = -u_base - u_turn
                speed_left = -u_base + u_turn

                good_apples = return_good(game_state['apples'])
                bad_apples = return_bad(game_state['apples'])
                if len(good_apples) > 0 and len(bad_apples) > 0:
                    state = State.IDLE
            
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