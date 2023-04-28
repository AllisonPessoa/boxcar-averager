#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 25 09:09:53 2022

@author: allison
"""
import serial
import time
import struct 

class TCSPC():
    def __init__(self, port='/dev/ttyACM1', boud=115200, timeout=5):
        self.ser = serial.Serial(port,boud,timeout)
        
        time.sleep(1)
    
    def get_BoxCar(self, gate_time, buffer_size, num_repetitions):
        b_gate = str(gate_time).encode('utf-8')
        b_buffer = str(buffer_size).encode('utf-8')
        b_rep = str(num_repetitions).encode('utf-8')
        
        self.ser.write(b'BXC '+ b_gate + b' ' + b_buffer + b' ' + b_rep)
        binary_data = self.ser.read(4*buffer_size) #32-bit input ARRAY
        counts_array = struct.unpack(str(buffer_size)+'i', binary_data)
        return counts_array
    
    def start_CounterMode(self, gate_time):
        b_gate = str(gate_time).encode('utf-8')
        self.ser.write(b'CNT_STR '+ b_gate)
        
    def get_counts(self):
        self.ser.write(b'CNT_GET')
        binary_data = self.ser.read(4) #single 32-bit input
        counts = struct.unpack('i', binary_data)
        return counts[0]
    
    def close(self):
        self.ser.close()
        
if __name__ == '__main__':
    Arduino = TCSPC(port='/dev/ttyACM0')