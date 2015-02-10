#!/usr/bin/env python 

import os, sys
import socket
import threading
import traceback
import struct
import time
import pickle
import ntpath
from packet import *
from array import array


class Peer(object):      
	# -----------------------------------------------------------------------------------*
	# inicializa as estruturas e variaveis essenciais para o arranque do programa
	# -----------------------------------------------------------------------------------*
	def __init__(self, configpath):
		# modo debug
		self.debug = True

		# lista de peers conhecidos
		self.peers = []

		# carregar ficheiro de configuracao
		if configpath: self.options = self.parseconfig(configpath)
		else: self.options = self.parseconfig('./p2p.conf')

		# endereco ip+porta do peer
		self.peeraddr = \
			(socket.gethostbyname(socket.gethostname()),int(self.options['port']))

		# inicia socket broadcast para a primitiva hello
		self.hsock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		self.hsock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		self.hsock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
		self.hsock.bind(('',int(self.options['helloport'])))

		# booleano para interromper o mainloop
		self.shutdown = False


	# -----------------------------------------------------------------------------------*
	# carrega ficheiro de configuracao para estrutura de armazenamento de opcoes e peers
	# -----------------------------------------------------------------------------------*
	def parseconfig(self, filename):
		options = {}
		comment_char = '#'
		option_char  = ['=',':']
		with open(filename) as f:
			for line in f:
				if comment_char in line:
					line, comment = line.split(comment_char, 1)
				for char in option_char:
					if char in line:
						option, value = line.split(char, 1)
						option = option.strip()
						value  = value.strip()
						if char == '=': 
							options[ option ] = value
						elif char == ':':
							self.peers.append((option,int(value)))
		return options

	
	# -----------------------------------------------------------------------------------*
	# loop principal do programa
	# -----------------------------------------------------------------------------------*
	def mainloop(self):
		self.__debug('Server started: %s:%s' % self.peeraddr)

		functions = [self.userinput,self.sendhello,self.recvhello]
		for f in functions:
			t = threading.Thread(target=f,args=[])
			t.daemon = True
			t.start()
		
		bsize = int(self.options['buffersize'])
		s = self.createsocket(int(self.options['port']))
		s.bind(('',int(self.options['port'])))
		
		while not self.shutdown:
			try:
				msg,addr = s.recvfrom(bsize+17)
				packet = Packet().dissemble(msg[:17])

				# CHUNK PRIMITIVE RECEIVED FROM CLIENT
				if packet[0] == 'G' and packet[2] == 0:
					self.__debug('[GET] Received request from peer %s:%s' % addr) 
					self.__debug('[GET] file: %s' % msg[17:])
					self.recvchunk(msg[17:],addr)

				# SEARCH PRIMITIVE RECEIVED FROM CLIENT
				elif packet[0] == 'S' and packet[2] == 0:
					self.__debug('[FIND] Received request from peer %s:%s' % addr)
					self.__debug('[FIND] file: %s' % msg[17:])
					self.recvsearch(msg[17:],addr)

			except KeyboardInterrupt:
				self.shutdown = True
				continue
			except IOError:
				pass
			except:
				if self.debug:
					traceback.print_exc()
					continue
		print '\nExiting P2P Application...'
		s.close()
		self.hsock.close()
		del s
		del self.hsock


	# -----------------------------------------------------------------------------------*
	# inicia um socket na porta passada como parametro
	# -----------------------------------------------------------------------------------*
	def createsocket(self, port):
		s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		return s


	# -----------------------------------------------------------------------------------*
	# executa comandos recebidos do terminal
	# -----------------------------------------------------------------------------------*
	def userinput(self):
		while not self.shutdown:
			try:
				str = raw_input('> ')
				if str[:3] == 'GET':
					self.sendchunk(str[4:])
				elif str[:4] == 'FIND':
					self.sendsearch(str[5:])
				elif str[:8] == 'REGISTER':
					self.register(str[9:])
				elif str[:4] == 'QUIT':
					self.shutdown = True
				else:
					print 'commands:\nGET <file.ext>\nFIND <file.ext>\n',
					print 'REGISTER <filepath>\nHELP\nQUIT'
			except KeyboardInterrupt:
				self.shutdown = True
				continue
			except:
				if self.debug:
					traceback.print_exc()
					continue
		self.__debug("EXITING USERINPUT")

	# -----------------------------------------------------------------------------------*
	# regista um ficheiro no sistema p2p (dado como argumento)
	# -----------------------------------------------------------------------------------*
	def register(self, filepath):
		try:
			with open('filelist.txt','a+') as f:
				fname = self.pathleaf(filepath)
				fsize = os.path.getsize(filepath)
				label = '%s:%s:%s\n' % (fname,filepath,fsize)
				f.write(label)
				print "[REGISTER] File '%s' registered successfully" % fname
		except EnvironmentError:
			print "[REGISTER] Error: file '%s' not found" % filepath
	
	# -----------------------------------------------------------------------------------*
	# transforma absolute-path em relative-path
	# -----------------------------------------------------------------------------------*
	def pathleaf(self, path):
		head, tail = ntpath.split(path)
		return tail or ntpath.basename(head)



# ---------------------------------------------------------------------------------------*
# PRIMITIVA SEARCH  ---------------------------------------------------------------------*
# ---------------------------------------------------------------------------------------*
	
	# -----------------------------------------------------------------------------------*
	# envia lista de ficheiros locais que fazem match com o nome de ficheiro solicitado
	# -----------------------------------------------------------------------------------*
	def recvsearch(self, filename, addr):
		matches = self.grep('filelist.txt',filename)
		if matches:
			s = self.createsocket(int(self.options['port']))
			packet = Packet('S',0,1,0,0,pickle.dumps(matches)).assemble()
			s.sendto(packet,addr)
			s.close()
			del s
		else:
			pass

	# -----------------------------------------------------------------------------------*
	# procura no sistema p2p por um ficheiro (dado como argumento)
	# -----------------------------------------------------------------------------------*
	def sendsearch(self, filename):
		peers = []
		s = self.createsocket(int(self.options['port']))
		bsize = int(self.options['buffersize'])
		packet = Packet('S',0,0,0,0,filename).assemble()
		for peer in self.peers:
			s.sendto(packet,peer)
			data, addr = s.recvfrom(bsize+17)
			for match in pickle.loads(data[17:]):
				fname,fpath,fsize = match[2].strip().split(':')
				print '[FIND] Received response from peer %s:%s' % addr
				print '[FIND] name: %s, path: %s, size: %s' % (fname, fpath, fsize)
			peers.append(addr)
		s.close()
		del s
		return peers

	# -----------------------------------------------------------------------------------*
	# procura na lista de ficheiros nomes que fazem match 
	# -----------------------------------------------------------------------------------*
	def grep(self, filename, needle):
		with open(filename) as f:
			matches = ((i, line.find(needle), line) for i, line in enumerate(f))
			return [match for match in matches if match[0] != -1]



# ---------------------------------------------------------------------------------------*
# PRIMITIVA CHUNK   ---------------------------------------------------------------------*
# ---------------------------------------------------------------------------------------*
	
	# -----------------------------------------------------------------------------------*
	# recebe chunks de dados de um peer
	# -----------------------------------------------------------------------------------*
	def recvchunk(self, filename, addr):
		s = self.createsocket(int(self.options['port']))
		bsize = int(self.options['buffersize'])
		with open(filename,'rb') as f:
			data = f.read()
		sent = 0
		seq = 1
		packet = Packet('G',seq,0,0).assemble()
		s.sendto(bytes(packet),addr)
		while data:
			packet = Packet('G',seq,1,0,0,data[:bsize]).assemble()
			s.sendto(bytes(packet),addr)
			seq  += 1
			sent += bsize
			print '\r[GET] %s bytes sent to peer' % sent, 
			data = data[bsize:]
		packet = Packet('G',seq,3).assemble()
		s.sendto(bytes(packet),addr)
		print "\n[GET] File '%s' sent successfully" % filename
		s.close()
		del s

	# -----------------------------------------------------------------------------------*
	# envia chunks de dados para um peer
	# -----------------------------------------------------------------------------------*
	def sendchunk(self, filename):
		s = self.createsocket(int(self.options['port']))
		bsize = int(self.options['buffersize'])
		data = []
		peernum, recsize, seq = 0, 0, 1
		packet = Packet('G',0,0,0,0,filename).assemble()
		for peer in self.peers:
			try:
				s.sendto(bytes(packet),peer)
				s.settimeout(1)
				syn,addr = s.recvfrom(17)
				packet = Packet().dissemble(syn[:17])
				if packet[2] == 0:
					peernum += 1
			except socket.error:
				continue
		with open('copy_'+filename,'wb') as f:
			while True:
				chunk, addr = s.recvfrom(bsize+17)
				packet = Packet().dissemble(chunk[:17])
				if packet[2] == 3: 
					# FIN
					break
			#	elif packet[2] == 2:
					# ACK
			#		packet = Packet('G',seq,2,0,0).assemble()
			#		self.sock.sendto(packet,addr)
				elif packet[2] == 1:
					# I
					recsize += bsize
					data[(packet[1]-1)*bsize:(packet[1])*bsize] = chunk[17:] #f.write(chunk[17:])
					print '\r[GET] %s bytes received' % recsize,
			f.writelines(data)
		print "\n[GET] File '%s' received successfully" % filename
		del data



# ---------------------------------------------------------------------------------------*
# PRIMITIVA HELLO   ---------------------------------------------------------------------*
# ---------------------------------------------------------------------------------------*
	
	# -----------------------------------------------------------------------------------*
	# envia pacote hello em broadcast para a rede local com lista de peers actual
	# -----------------------------------------------------------------------------------*
	def sendhello(self):
		while not self.shutdown:	
			try:
				peerlist = self.peers[:]
				peerlist.append(self.peeraddr)
				packet = Packet('H',0,0,0,0,pickle.dumps(peerlist)).assemble()
				self.hsock.sendto(packet,("<broadcast>",int(self.options['helloport'])))
				time.sleep(int(self.options['t1']))
			except KeyboardInterrupt:
				self.shutdown = True
				continue
			except:
				if self.debug:
					traceback.print_exc()
					continue
		self.__debug("EXITING SENDHELLO")

	# -----------------------------------------------------------------------------------*
	# recebe pacote hello com nova lista de peers
	# -----------------------------------------------------------------------------------*
	def recvhello(self):
		while not self.shutdown:	
			try:
				chunk,addr = self.hsock.recvfrom(int(self.options['buffersize']))
				for peer in pickle.loads(chunk[17:]):
					if self.addpeer(peer):
						self.__debug("New peer added to the peerlist: %s:%s" % peer)
			except KeyboardInterrupt:
				self.shutdown = True
				continue
			except:
				if self.debug:
					traceback.print_exc()
					continue
		self.__debug("EXITING RECVHELLO")

	# -----------------------------------------------------------------------------------*
	# adiciona novo peer na estrutura
	# -----------------------------------------------------------------------------------*
	def addpeer(self, addr):
		if addr not in self.peers and self.peeraddr != addr:
			self.peers.append(addr)
			return True
		else:
			return False



# ---------------------------------------------------------------------------------------*
# DEBUG             ---------------------------------------------------------------------*
# ---------------------------------------------------------------------------------------*
	
	# -----------------------------------------------------------------------------------*
	# imprime mensagens para fazer debug
	# -----------------------------------------------------------------------------------*
	def __debug(self, msg):
		if self.debug: print msg



if __name__ == '__main__':
	configpath = sys.argv[1] if len(sys.argv) > 2 else None
	Peer(configpath).mainloop()

