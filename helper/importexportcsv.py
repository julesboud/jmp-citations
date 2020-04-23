# -*- coding: utf-8 -*-
"""
Custom module to import and export csv row by row.
"""


import os
from collections import OrderedDict

class ExportCSV:
    '''
    Class to import from and export to CSV (to and from dict) with semi-colon as separator.
    '''
    def __init__(self, fileName, headers=None, resetFile=False, encoding='utf-8-sig', sep=';'):
        self.fileName = fileName
        self.encoding = encoding
        self.sep = sep
        if not os.path.isfile(fileName) or resetFile:
            # Will create/reset the file as per the evaluation of above condition
            fOut = open(fileName, 'w', encoding=self.encoding)
            fOut.close()
        fIn = open(fileName) # Open file if file already present
        self.inString = fIn.read()
        fIn.close()
        if len(self.inString) <= 0: # If File already exsists but is empty, it adds the header
            fOut = open(fileName, 'w', encoding=self.encoding)
            fOut.write(sep.join(headers)+'\n')
            fOut.close()

    def write_csv(self, array):
        fOut = open(self.fileName, 'a+', encoding=self.encoding)
        # Individual elements are dictionaries
        writeString = ''
        try:
            if isinstance(array,dict):
                for field in array:
                    writeString += str(array[field]) + self.sep
            if isinstance(array,list):
                for element in array:
                    writeString += str(element) + self.sep

            writeString = writeString[:-1]
            writeString += '\n'
            print(writeString)
            fOut.write(writeString)

        except Exception as e:
            print(e)
            fOut.write('FAILED_TO_WRITE\n')
        fOut.close()


class ImportCSV:
    def __init__(self, fileName, headers=None, encoding='utf-8-sig', sep=';', errors_handling = 'strict'):
        self.fileName = fileName
        self.headers = headers
        self.encoding = encoding
        self.sep = sep
        self.errors_handling = errors_handling
        if not os.path.isfile(fileName):
            print('There is no such file in folder.')
            raise Exception
        fIn = open(fileName, 'r', encoding = self.encoding, errors = errors_handling) # Open file if file already present
        inString = fIn.read()
        if not inString:
            print('File is empty.')
            raise Exception
        fIn.close()

    def read_csv(self):
        fIn = open(self.fileName, 'r', encoding = self.encoding, errors= self.errors_handling)
        if self.headers == None:
            headers = fIn.readline()[:-1].split(self.sep)
        else:
            headers = self.headers
        list_of_dict = []
        i=1
        while i==1:
            obs = fIn.readline()[:-1].split(self.sep)
            if obs==['']:
                break
            dict_temp = OrderedDict(zip(headers,obs))
            list_of_dict.append(dict_temp)
        return list_of_dict
