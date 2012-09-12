#!/usr/bin/python
import random
import Image
import sys
from math import sqrt
import argparse

############
	#PUT
############
def put(coverFile, messageFile, density, password, filter, battlesteg):

	#Attempt to open the provided image, handling all IO exceptions
	try:
		cover = Image.open(coverFile)
	except IOError as e:
		sys.exit("File does not exist or is in use - please check your cover file and try again")

	#Create a copy of the image and extract the pixel data and dimensions
	steg = cover.copy()
	pix = steg.load()
	MAX_WIDTH, MAX_HEIGHT = steg.size
	
	#Check density is non-empty (caught by argparse, but required for library use)
	if (density == None):
		density = 1
	
	#Create a list of valid pixel coordinates. When not using a filter, this is every coordinate
	#When using a filter, only the noisiest parts of the image are used
	if (filter == None):
		coords = [(x, y) for y in range(MAX_HEIGHT) for x in range(MAX_WIDTH)]
	elif (density > 7):
		sys.exit("Density cannot exceed 7 while using a filter")
	else:
		#Threshold of the filters are dynamically calculated, relative to the density at which the message is stored
		if(filter == "gradient"):
			coords = gradientFilter(pix, density, 1000/pow(2, density), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "gradient_strict"):
			coords = gradientFilter(pix, density, 1000/(0.5*pow(2, density)), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "laplace"):
			coords = laplaceFilter(pix, density, 1000/pow(2, density), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "laplace_strict"):
			coords = laplaceFilter(pix, density, 1000/(0.1*pow(2, density)), MAX_WIDTH, MAX_HEIGHT)
		else:
			sys.exit("Invalid filter type")
	
	if(battlesteg):
		if(filter == None):
			sys.exit("To perform a battlesteg algorithm, a filter must also be selected.")
		else:
			coords = battlestegFilter(coords, password, MAX_WIDTH, MAX_HEIGHT)
	else:
		coords = shuffleCoords(password, coords, MAX_WIDTH, MAX_HEIGHT)
	
	#Calculate the potential capacity of the image (up to a maximum of 16,777,216 at density 1, as the length is stored in 3 bytes)
	capacity = min(2**(24*density) - 1, ((((len(coords) * density * 3)/8)-8)-((3*density)-8)))
	if (capacity <= 0):
		sys.exit("This image cannot hold a message (with the current settings). Try changing the settings, or use a larger image, with less areas of flat color")
	message = getMessage(messageFile, capacity)
	
	#Get the initial coordinates
	x, y = getXY(coords)
		
	#Encode the length of the message as a 24 bit binary int (proportional to the density of encoding)
	length = "{0:00"+str(24*density)+"b}"
	length = length.format(len(message))

	r = []
	g = []
	b = []

	#Add each bit of the binary string to an array, of max length: density
	for bit in length:
		if (len(r) < density):
			r.append(bit)
		elif (len(g) < density):
			g.append(bit)
		elif (len(b) < density):
			b.append(bit)

			#When all arrays are full, replace the LSB(s) of the current pixel with those in the arrays
			if(len(b) == density):
				pix[x,y] = (modifyBits(pix[x,y][0], r), modifyBits(pix[x,y][1], g), modifyBits(pix[x,y][2], b))
			
				#Get the next coordinate and clear the arrays
				x, y = getXY(coords)

				r = []
				g = []
				b = []
	
	#Take note of how many characters have been hidden, for error reporting purposes
	hiddenChars = 0
	error = False
	
	try:
		#Convert each character of the message into an 8 bit binary string
		for char in message:
			hiddenChars += 1
			binary = "{0:08b}".format(ord(char))
			
			#Add each bit of the binary string to an array, of max length: density
			for bit in binary:
				if (len(r) < density):
					r.append(bit)
				elif (len(g) < density):
					g.append(bit)
				elif (len(b) < density):
					b.append(bit)
					
					#When all arrays are full, replace the LSB(s) of the current pixel with those in the arrays
					if(len(b) == density):
						pix[x,y] = (modifyBits(pix[x,y][0], r), modifyBits(pix[x,y][1], g), modifyBits(pix[x,y][2], b))
						
						#Get the next coordinate and clear the arrays
						x, y = getXY(coords)

						r = []
						g = []
						b = []
		
		#If any bits remain in the array, replace the LSB(s) of the current pixel with those in the arrays
		if(len(r) != 0):
			if(len(g) != 0):
				if(len(b) != 0):
					pix[x,y] = (modifyBits(pix[x,y][0], r), modifyBits(pix[x,y][1], g), modifyBits(pix[x,y][1], b))
				else:
					pix[x,y] = (modifyBits(pix[x,y][0], r), modifyBits(pix[x,y][1], g), pix[x,y][2])
			else:
				pix[x,y] = (modifyBits(pix[x,y][0], r), pix[x,y][1], pix[x,y][2])
	except Exception as e:
		error = True
	
	#Inform the user how many characters were successfully (or unsuccessfully) hidden and save the image
	print str(hiddenChars)+" characters succesfully hidden."
	if (error):
		print str(len(message) - hiddenChars)+" characters were NOT succesfully hidden. This message may be irretrievable. Try again, or, if the problem persists, contact an developer"
		
	saveImage(steg)

############
	#GET
############
def get(coverFile, messageFile, density, password, filter, battlesteg):

	#Attempt to open the provided image, handling all IO exceptions
	try:
		cover = Image.open(coverFile)
	except IOError as e:
		sys.exit("File does not exist or is in use - please check your cover file and try again")
	
	#If a message file is provided open/create it for writing
	if(messageFile != None):
		try:
			textFile = open(messageFile, 'w')
		except IOError as e:
			sys.exit("File does not exist or is in use - please check your message file and try again")
	
	#Extract the pixel data and dimensions
	pix = cover.load()
	MAX_WIDTH, MAX_HEIGHT = cover.size
	
	#Check density is non-empty (caught by argparse, but required for library use)
	if (density == None):
		density = 1
	
	#Create a list of valid pixel coordinates. When not using a filter, this is every coordinate
	#When using a filter, only the noisiest parts of the image are used
	if (filter == None):
		coords = [(x, y) for y in range(MAX_HEIGHT) for x in range(MAX_WIDTH)]
	elif (density > 7):
		sys.exit("Density cannot exceed 7 while using a filter")
	else:
		#Threshold of the filters are dynamically calculated, relative to the density at which the message is stored
		if(filter == "gradient"):
			coords = gradientFilter(pix, density, 1000/pow(2, density), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "gradient_strict"):
			coords = gradientFilter(pix, density, 1000/(0.5*pow(2, density)), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "laplace"):
			coords = laplaceFilter(pix, density, 1000/pow(2, density), MAX_WIDTH, MAX_HEIGHT)
		elif (filter == "laplace_strict"):
			coords = laplaceFilter(pix, density, 1000/(0.1*pow(2, density)), MAX_WIDTH, MAX_HEIGHT)
		else:
			sys.exit("Invalid filter type")
	
	if(battlesteg):
		if(filter == None):
			sys.exit("To perform a battlesteg algorithm, a filter must also be selected.")
		else:
			coords = battlestegFilter(coords, password, MAX_WIDTH, MAX_HEIGHT)
	else:
		coords = shuffleCoords(password, coords, MAX_WIDTH, MAX_HEIGHT)

	#Get the initial coordinates
	x, y = getXY(coords)
	
	
	length = ''
	#Read the LSB(s) of the first 24 bytes
	for i in range(8):
		length += readBits(pix[x,y][0], density)
		length += readBits(pix[x,y][1], density)
		length += readBits(pix[x,y][2], density)
		
		x, y = getXY(coords)

	#Convert the obtained string to a base 10 int
	length = int(length, 2)
	
	#Initialise strings to store the message in binary form, and ascii form
	binary_message = ''
	message = ''

	#Given the length of the message, read the appropriate amount of LSBs
	for i in range(((((length)*8)+4)/density)/3):
	
		binary_message += readBits(pix[x,y][0], density)
		binary_message += readBits(pix[x,y][1], density)
		binary_message += readBits(pix[x,y][2], density)
		
		x, y = getXY(coords)
		
		#Convert the binary string to ascii
		if (len(binary_message) >= 8):
			for j in range(len(binary_message)/8):
				char = binary_message[:8]
				binary_message = binary_message[8:]
				message += chr(int(char, 2))

	#Either save the message to the provided text file or print it to the screen
	if(messageFile != None):
		textFile.write(message)
		textFile.close()	
	else:
		print "The message is:"
		print message

############
	#ANA
############

def ana(filename):

	#Attempt to open the provided image, handling all IO exceptions
	try:
		cover = Image.open(filename)
	except IOError as e:
		sys.exit("File does not exist - please check your cover file and try again")

	#Create a copy of the image and extract the pixel data and dimensions
	analysis = cover.copy()
	pix = analysis.load()
	MAX_WIDTH, MAX_HEIGHT = analysis.size
	AMPLIFY = 1
	
	#For each colour of each pixel, read the LSB. If it is 0, set the entire colour to 0. If it is 1, set the entire colour to 255
	for x in range(MAX_WIDTH):
		for y in range(MAX_HEIGHT):
			if (readBits(pix[x, y][0], AMPLIFY) == "0"):
				r = 0
			else:
				r = 255
				
			if (readBits(pix[x, y][1], AMPLIFY) == "0"):
				g = 0
			else:
				g = 255	
				
			if (readBits(pix[x, y][2], AMPLIFY) == "0"):
				b = 0
			else:
				b = 255
			pix[x, y] = (r, g, b)
	
	#Save the image and notify the user
	saveImage(analysis)
	print "Analysis complete"
		
############
	#MISC
############
def modifyBits(denary, bits):
	assert 1 <= len(bits) <= 8
	assert 0 <= denary <= 255

	#Convert the provided base 10 number "denary" to an 8 bit (0 padded) binary string
	binary = bin(denary)
	binary = binary[2:]
	for i in range(8-len(binary)):
		binary = "0" + binary
	
	#Replace the LSB(s) with the provided binary string "bits"
	binary = binary[:len(bits)*-1]
	for b in range(len(bits)-1, -1, -1):
		assert bits[b] == '0' or bits[b] == '1'
		binary += bits[b]
	
	#Convert back to base 10 and return
	return int(binary, 2)

def readBits(denary, num_bits):
	assert 1 <= num_bits <= 8
	assert 0 <= denary <= 255
	
	#Convert the provided base 10 number "denary" to an 8 bit (0 padded) binary string
	binary = bin(denary)
	binary = binary[2:]
	for i in range(8-len(binary)):
		binary = "0" + binary
	
	#Return the last "num_bits" number of LSB(s)
	binary = binary[num_bits*-1:]
	binary = binary[::-1]
	return binary
	
def stripLSBs(denary, density):
	assert 0 <= denary <= 255
	assert 1 <= density <= 7
	
	#Convert the provided base 10 number "denary" to an 8 bit (0 padded) binary string
	binary = bin(denary)
	binary = binary[2:]
	for i in range(8-len(binary)):
		binary = "0" + binary
	
	#Replace the used LSBs with 0s, convert back to base 10 and return
	binary = binary[:-density]+"000000"
	return int(binary, 2)

def gradientFilter(image, density, threshold, MAX_WIDTH, MAX_HEIGHT):
	filterCoords = []
		
	#For each colour of each pixel (barring the extreme edges):
	for x in range(1, MAX_WIDTH-1):
		for y in range(1, MAX_HEIGHT-1):
			
			#Calculate the standard deviation, using only the unused MSBs of each colour
			rdx = (stripLSBs(image[x+1,y][0], density) - stripLSBs(image[x-1,y][0], density))/2
			rdy = (stripLSBs(image[x,y+1][0], density) - stripLSBs(image[x,y-1][0], density))/2
			
			gdx = (stripLSBs(image[x+1,y][1], density) - stripLSBs(image[x-1,y][1], density))/2
			gdy = (stripLSBs(image[x,y+1][1], density) - stripLSBs(image[x,y-1][1], density))/2
			
			bdx = (stripLSBs(image[x+1,y][2], density) - stripLSBs(image[x-1,y][2], density))/2
			bdy = (stripLSBs(image[x,y+1][2], density) - stripLSBs(image[x,y-1][2], density))/2
			
			#Take the root of the sum the squares to calculate the magnitude of the gradient
			value = sqrt( rdx*rdx + gdx*gdx + bdx*bdx + rdy*rdy + gdy*gdy + bdy*bdy )
			
			#If the value is above a given threshold, add it to the list of coordinates
			if(value > threshold):
				filterCoords.append((x, y))

	return filterCoords
	
def laplaceFilter(image, density, threshold, MAX_WIDTH, MAX_HEIGHT):
	filterCoords = []

	#For each colour of each pixel (barring the extreme edges):
	for x in range(1,MAX_WIDTH-1):
		for y in range(1,MAX_HEIGHT-1):
		
			#Calculate the second derivative, using only the unused MSBs of each colour
			rdx = stripLSBs(image[x+1,y][0], density) + stripLSBs(image[x-1,y][0], density) - 2*stripLSBs(image[x,y][0], density)
			rdy = stripLSBs(image[x,y+1][0], density) + stripLSBs(image[x,y-1][0], density) - 2*stripLSBs(image[x,y][0], density)
			
			gdx = stripLSBs(image[x+1,y][1], density) + stripLSBs(image[x-1,y][1], density) - 2*stripLSBs(image[x,y][1], density)
			gdy = stripLSBs(image[x,y+1][1], density) + stripLSBs(image[x,y-1][1], density) - 2*stripLSBs(image[x,y][1], density)
			
			bdx = stripLSBs(image[x+1,y][2], density) + stripLSBs(image[x-1,y][2], density) - 2*stripLSBs(image[x,y][2], density)
			bdy = stripLSBs(image[x,y+1][2], density) + stripLSBs(image[x,y-1][2], density) - 2*stripLSBs(image[x,y][2], density)
			
			#Take the root of the sum the squares to calculate the magnitude of the gradient
			value = sqrt( rdx*rdx + gdx*gdx + bdx*bdx + rdy*rdy + gdy*gdy + bdy*bdy )
			
			#If the value is above a given threshold, add it to the list of coordinates
			if(value > threshold):
				filterCoords.append((x, y))

	return filterCoords
	
def battlestegFilter(filterCoords, password, MAX_WIDTH, MAX_HEIGHT):
	#Define how many extra "shots" are to be taken, withing what range
	extraShots = 15
	withinRange = 5
	
	#Create a list of all coords in the image
	coords = [(x, y) for y in range(MAX_HEIGHT) for x in range(MAX_WIDTH)]
	
	#Create a password if none is given, and use it to randomise the coordinates
	if (password == None):
		password = "WowLookatThisreallySecureString"+str(len(filterCoords))
	
	random.seed(password)
	random.shuffle(coords)
	
	newCoords = []
	
	#While there are unused coordinates:
	while (len(coords)>0):
	
		#Take a shot
		value = coords.pop(0)
		newCoords.append(value)
		
		#If the shot is a "hit":
		if (value in filterCoords):
			filterCoords.remove(value)
			
			#Make extra shots using the given range
			for i in range(extraShots):
				x = random.randint(max(0, value[0]-withinRange), min(MAX_WIDTH, value[0]+withinRange))
				y = random.randint(max(0, value[1]-withinRange), min(MAX_HEIGHT, value[1]+withinRange))
				
				if ((x, y) in coords):
					coords.remove((x, y))
					if ((x, y) in filterCoords):
						filterCoords.remove((x, y))
					newCoords.append((x, y))
					
	return newCoords
				
def getMessage(messageFile, capacity):
	#If no message file is provided, display how many characters the image can hold. If the provided message is over this limit, request the user
	#enters a new message and restate the capacity
	if (messageFile == None):
		print "This image can hold a message of up to {0} (ASCII) characters.".format(capacity)
		message = raw_input("Enter the secret message now: ")
		while(len(message) > capacity):
			message = raw_input("Message is too long - please shorten the message to {0} (ASCII) characters: ".format(capacity))
	
	#If a message file is provided, make sure it exists, is available for use, is not empty, and is not over the allowed capacity.
	else:
		try:
			messageFile = open(messageFile)
		except IOError as e:
			sys.exit("File does not exist or is already in use - please check your message file and try again")

		message = messageFile.read()
		messageFile.close()

		if (len(message) == 0):
			sys.exit("File is empty - please check your message file and try again")
		elif (len(message) > capacity):
			sys.exit("File is too large - your message was "+str(len(message))+" characters but at this density, this image can only hold "+str(capacity)+" characters. Please try again using either a larger image, a higher density, or a smaller message.")	
	return message
			
def shuffleCoords(password, coords, MAX_WIDTH, MAX_HEIGHT):
	#Create a default password if none is provided
	if (password == None):
		password = "WowLookatThisreallySecureString"+str(MAX_WIDTH)+str(MAX_WIDTH*MAX_HEIGHT)
	
	#Use the password to seed a psedorandom number generator and shuffle the coordinate list
	random.seed(password)
	random.shuffle(coords)
	return coords

def getXY(coords):
	#Get the next x and y coordinates
	xy = coords.pop(0)
	return (xy[0], xy[1])
	
def saveImage(image):
	#Save the given image as a .bmp or .png
	save = raw_input("Save image as: ")
	while((save.count(".") != 1) or (not (save[-4:] == ".bmp" or save[-4:] == ".png"))):
		save = raw_input("Please save the image as a .bmp or .png: ")
	image.save(save)

##################
	#INTERFACE
##################
		
#Create a parser for the following arguments:
def make_parser():
	parser = argparse.ArgumentParser(description='Put, Get or Analyse a hidden message')
	group = parser.add_mutually_exclusive_group(required=True)
	
	#Required (and mutually exclusive) arguments:
	#PUT a hidden message into an image
	#GET a hidden message from an image
	#ANAlyse an image for a hidden message
	group.add_argument('--put', type=image_file)
	group.add_argument('--get', type=image_file)
	group.add_argument('--ana', type=image_file)
	
	#Additional (optional) arguments:
	#The density at which to hide the data (up to a maximum of eight bits per byte)
	parser.add_argument('-d', required=False, type=int, default=1, choices=range(1, 9))
	#A user-specificed password
	parser.add_argument('-p', required=False)
	
	#A text file, either containing a message to embed, or to store a retrieved message
	parser.add_argument('-m', required=False, type=text_file)
	
	#A filter to be applied so that the noisiest sections of the image are used
	parser.add_argument('-f', required=False, choices=["gradient", "laplace", "gradient_strict", "laplace_strict"])
	
	#Whether to use a battlesteg algorithm
	parser.add_argument('-b', required=False)
	return parser

#Type checker for images - currently, only .BMP and .PNG formats are supported.
def image_file(string):
	if (not (string[-4:] == ".bmp" or string[-4:] == ".png")):
		msg = "Only .bmp and .png files are accepted"
		raise argparse.ArgumentTypeError(msg)
	return string
	
#Type checker for text files - only .TXT files are supported
def text_file(string):
	if (string[-4:] != ".txt"):
		msg = "Only .txt files are accepted"
		raise argparse.ArgumentTypeError(msg)
	return string

############
	#MAIN
############
	
if __name__=='__main__':
	parser = make_parser()
	args = parser.parse_args()

	#If the user is attempting to PUT a message, pass the necessary arguments to the tools and
	#handle any exceptions
	if args.put != None:
		try:
			put(args.put, args.m, args.d, args.p, args.f, args.b)
		except Exception as e:
			print "An error occured while trying to hide the message. If the problem persists, inform a developer of the error below:"
			print e
			
	#If the user is attempting to GET a message, pass the necessary arguments to the tools and
	#handle any exceptions
	elif args.get != None:
		try:
			get(args.get, args.m, args.d, args.p, args.f, args.b)
		except Exception as e:
			print "An error occured while trying to retrieve the message. There may be no message to find - alternatively, please check your parameters are correct. If the problem persists, inform a developer of the error below:"
			print e
			
	#If the user is attempting to ANA an image, pass the necessary arguments to the tools and
	#handle any exceptions
	elif args.ana != None:
		try:
			ana(args.ana)
		except Exception as e:
			print "An error occured while trying to analyse this image. If the problem persists, inform a developer of the error below:"
			print e
			
	#If none of the above, user is missing a mandatory argument
	#(This is handled above by argparse, but is included here for completeness)
	else:
		sys.exit("Please specify an argument: --put, --get or --ana")