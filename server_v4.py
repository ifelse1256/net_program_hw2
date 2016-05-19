import socket
from threading import Thread
import time

endSuffix_str = ' EOF'
endSuffix = b' EOF'
cut_tag = '#^'
user_list = []
SOCK_LISTEN = []
FILE_LISTEN = []
def mesg_rm_endSuffix(login_reply):
	global endSuffix_str
	index = login_reply.find(endSuffix_str)
	return login_reply[0:index]

def mesg_encode(mesg):
	mesg = str(mesg)
	mesg +=endSuffix_str
	mesg = mesg.encode()
	return mesg
def mesg_decode(mesg):
	mesg = mesg.decode()
	mesg = str(mesg)
	mesg = mesg_rm_endSuffix(mesg)
	mesg_list = mesg.split(cut_tag)
	return mesg_list

def create_server_socket(bind_address):
	port = 6666
	listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # listening socket
	listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allowing to reuse address
	listener.bind((bind_address,port))
	listener.listen(1)  # turning  the socket into a passively listening socket
	print ('Listening at {}'.format(bind_address))
	return listener

def accept_conn(listener):
	global cut_tag, user_list
	
	sock, address = listener.accept()
	print ('Accepted connecntion from {}'.format(address))
	
	file_lock = False
	th_user = ''
	th_userIndex = -1
	while True:
		# Converse with a client over sock until they are done talking
		message_b = recvall(sock,4096)
		op_part_list = mesg_decode(message_b)
		print ('data:',op_part_list)
		#print ('message : {0}'.format(op_part_list))
		if op_part_list[0] == 'login':
			for user in user_list:
				if (op_part_list[1] == user.account) and (op_part_list[2] == user.passwd) and (user.status == False):
					mesg = 'TRUE'
					if len(user.off_mesg)>0:
						mesg += cut_tag
						for off_mesg in user.off_mesg:
							mesg +=off_mesg

					
					print ('message:',mesg)
					mesg_b =mesg_encode(mesg)
					sock.sendall(mesg_b)

					th_user = user.account
					th_userIndex = user.id
					
					user.status = True
					user.sock = sock  #sava connection
					user.addr = address[0]
					user.port = address[1]
					
					# operation
					modify_status_for_friend(th_user,True) # update other's friend list status
					# offline message
					
				else:
					pass

			if th_userIndex == -1 :
				mesg = 'loging is wrong...'
				mesg_b = mesg_encode(mesg)
				sock.sendall(mesg_b)
				try:
					sock.close()
				except EOFError:
					print(mesg)
				except OSError:
					print(mesg)
	
		elif op_part_list[0] == 'logout':

			if user_list[th_userIndex].status == True :
				user.status = False
				modify_status_for_friend(th_user,False)
			try:
				sock.close()
			except EOFError:
				print('user logout...')
	
		elif op_part_list[0] == 'friend' and user_list[th_userIndex].status == True:
			
			if op_part_list[1] == 'list':
				friend_num = user_list[th_userIndex].friend_num()
				mesg = 'friend_list'
				print ('number:',friend_num)
				for i in range(friend_num):
					user = user_list[th_userIndex]
					data = cut_tag+str(user.friend_list[i])+':'+str(user.friend_status[i])
					mesg = mesg + data
				
				mesg_b = mesg_encode(mesg)
				sock.sendall(mesg_b)

			elif op_part_list[1] == 'add':
				add_friend_name = op_part_list[2]
				mesg = 'not have this number...'
				for user in user_list:
					if user.account == add_friend_name and user.account != user_list[th_userIndex].account:
						mesg = 'add Successful...'
						user_list[th_userIndex].add_friend(add_friend_name,user.status)
						break
				mesg_b = mesg_encode(mesg)
				sock.sendall(mesg_b)

			elif op_part_list[1] == 'rm':
				rm_friend_name = op_part_list[2]
				result = user_list[th_userIndex].rm_friend(rm_friend_name)
				if result>-1:
					mesg = 'rm successful...'
				else:
					mesg = 'you not have this friend...'
				mesg_b = mesg_encode(mesg)
				sock.sendall(mesg_b)
			
			else:
				mesg = 'error_instruction'
				mesg_b = mesg_encode(mesg)
				sock.sendall(mesg_b)

		elif op_part_list[0] == 'send' and user_list[th_userIndex].status == True:
			rece_name = op_part_list[1]
			#count = 0
			#rebuild message
			print ('rece name:',rece_name)
			message = off_on_message(user_list[th_userIndex].account, op_part_list)
			for user in user_list:
				if user.account == rece_name and user.status == True: ## on_line mesg
					#send to receive's Message Queue
					mesg_b = mesg_encode(message)
					user.send_message(mesg_b)
					#reply to sender
					message = 'has_sent_to_'+user.account
					mesg_b = mesg_encode(message)
					sock.sendall(mesg_b)
					break
				elif user.account == rece_name and user.status == False: ## off_line mesg
					#send to receive's class
					user.off_message(user_list[th_userIndex].account,message)
					#reply to sender
					message = 'has_sent_to_'+user.account
					mesg_b = mesg_encode(message)
					sock.sendall(mesg_b)
					break
				#count +=1

		elif op_part_list[0] == 'sendfile' and user_list[th_userIndex].status == True:
			#recevive file instruction
			rece_name = op_part_list[1]
			filename = op_part_list[2]
			file_data = recvall(sock,4096) 

			for user in user_list :
				if user.account == rece_name:
					rece_user = user
			
			#send to target mesg for acception?
			mesg = 'FileFrom'+cut_tag+user_list[th_userIndex].account+cut_tag+filename
			mesg_b = mesg_encode(mesg)
			rece_user.send_message(mesg_b)

			while True:
				time.sleep(1)
				if len(FILE_LISTEN) > 0:
					reply = FILE_LISTEN.pop()
					break

			if reply == 'N' or reply == 'n':
				file_data = ''
				mesg = 'snedfile'+cut_tag+'denied'+cut_tag+':receiver'+cut_tag+'denied..'
				sock.sendall(mesg_encode(mesg))
			elif reply == 'Y' or reply == 'y':
				#rece_user.send_message(file_data)
				mesg = 'sendfile'+cut_tag+'accept'+cut_tag+':'+rece_user.account+cut_tag+'accpet..'
				sock.sendall(mesg_encode(mesg))
				rece_user.sock.sendall(file_data) #send the file to receive
		

		elif op_part_list[0] == 'FileReply':
				FILE_LISTEN.append(str(op_part_list[1]))
				print('server :',op_part_list[1])
		else:
			mesg = 'Error_instruction'
			mesg_b = mesg_encode(mesg)
			sock.sendall(mesg_b)
def off_on_message(send_name,mesgPart_list):
	global cut_tag
	message ='from'+cut_tag+send_name+',message:'+cut_tag
	for i in range(2,len(mesgPart_list),1):
		message += mesgPart_list[i]
		message += ' '
	print ('Mssg:',message)
	return message



def  recvall(sock,length):
	global endSuffix
	data = b''
	message_b = sock.recv(length)
	
	if not message_b:
		raise EOFError('socket close...')
	while not message_b.endswith(endSuffix):
		data = sock.recv(length)
		if not data:
			raise EOFError('socket close...')
		message_b +=data

	return message_b


def start_thread(listener, workers=4):
	num_thread = (listener,)
	for i in range(workers):
		Thread(target= accept_conn,args=num_thread).start()


def modify_status_for_friend(name,status):
	for user in user_list:
		if user.account !=name:
			user.friend_status_change(name,status)


class USER:
	def __init__(self):
		self.id = 0
		self.account = ''
		self.passwd = ''
		self.sock = ''
		self.status = False
		self.friend_list = []
		self.friend_status =[]
		self.off_mesg = []
		self.addr = ''
		self.port = 0
	def add_friend(self, friend_name, status):
		self.friend_list.append(friend_name)
		self.friend_status.append(status)

	def rm_friend(self,friend_name):
		try:
			friend_index = self.friend_list.index(friend_name)
			print('index:', friend_index)
		except ValueError:
			friend_index =-1
		finally:
			if friend_index>-1:
				garbage = self.friend_list.pop(friend_index)
				garbage = self.friend_status.pop(friend_index)
		return friend_index

	def friend_num(self):
		if len(self.friend_list) == len(self.friend_status):
			number = len(self.friend_list)
		else:
			number =-1
		return number

	def off_message(self,from_friend,mesg):
		#mesg = cut_tag+'from'+cut_tag+from_friend+cut_tag+',mesg:'+cut_tag+mesg
		self.off_mesg.append(mesg)
	
	def send_message(self,message):
		self.sock.sendall(message)
	def rece_message(self,length):
		global endSuffix
		data = b''
		message_b = self.sock.recv(length)
		print ('messageb:',message_b)
	
		if not message_b:
			raise EOFError('socket close...')
		while not message_b.endswith(endSuffix):
			data = self.sock.recv(length)
			if not data:
				raise EOFError('socket close...')
			message_b +=data

		return message_b
	
	def friend_status_change(self, name,status):
		try:
			friend_index = self.friend_list.index(name)
		except ValueError:
			friend_index = -1
		finally:
			if friend_index > -1:
				self.friend_status[friend_index] = status



def catch_user_data():
	temp_list = []
	for i in range(4) :
		temp_list.append(USER())
		temp_list[i].id = i
		i += 1
	temp_list[0].account = 'nick'
	temp_list[0].passwd = 'testn'
	temp_list[0].add_friend('kely',False)
	
	temp_list[1].account = 'kely'
	temp_list[1].passwd = 'testk'
	temp_list[1].add_friend('nick',False)
	temp_list[1].add_friend('john',False)
	
	temp_list[2].account = 'john'
	temp_list[2].passwd = 'testj'
	temp_list[2].add_friend('kely',False)

	temp_list[3].account = 'mary'
	temp_list[3].passwd = 'testm'

	print ('user data initial successful...')
	return temp_list



if __name__ == '__main__':
	global user_list
	address = '127.0.0.1'
	user_list = catch_user_data()
	listener = create_server_socket(address)
	start_thread(listener)

