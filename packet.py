#!/usr/bin/env python 

import struct

class Packet(object):

	"""
	CMD:
	HELLO  = H
	GET    = G
	CHUNK  = C
	SEARCH = S

	FLAGS:
	SYN = 0
	I   = 1
	ACK = 2
	FIN = 3
	"""

	def __init__(self,cmd='',seq=0,flag=0,offset=0, \
										size=0,data=''):
		self.cmd    = cmd
		self.seq    = seq
		self.flag   = flag
		self.offset = offset
		self.size   = size
		self.data   = data

	def assemble(self):
		p = struct.pack('!cIIII',self.cmd,self.seq, \
						self.flag,self.offset,self.size)
		return p + self.data
		
	def dissemble(self,packet):
		format = struct.Struct('!cIIII')
		unpacked = format.unpack(packet)
		return unpacked
