import glob, os, re, sys, time
from collections import OrderedDict

#Import custom class from module in same folder. Has methods read() and write().
from importexportcsv import ExportCSV, ImportCSV
from unaccent import unaccent
import pandas as pd

import pdfminer
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator

from nltk.tokenize import word_tokenize
from nltk.tag.stanford import StanfordNERTagger

import mysql.connector
from mysql.connector import Error

#Set (absolute) location of Stanford NER files and java application.
jar=r'.\stanford-ner\stanford-ner.jar'
model=r'.\stanford-ner\classifiers\english.all.3class.distsim.crf.ser.gz'
java_path = r'C:\\Program Files\Java\jre1.8.0_211\bin\java.exe'
os.environ['JAVAHOME'] = java_path
st=StanfordNERTagger(model,jar,encoding='utf8')

def sql_query_pandas(query):
    '''
    Returns the results of an sql query.
    Can be returned either in buffered cursor form or in a pandas dataframe.
    '''
    try:
        connection = mysql.connector.connect(host='127.0.0.1',
                                                 database='ftrecruiter',
                                                 user='www',
                                                 password='1www',
                                                 use_pure=True)

        if connection.is_connected():
            #db_Info = connection.get_server_info()
            print("Connected to MySQL database... ")
            query_df = pd.read_sql_query(query, connection)
            return query_df

    except Error as e :
        print ("Error while connecting to MySQL", e)

def import_journals_list(journals_file_path):
        journals_file = open(journals_file_path, 'r', encoding='utf-8-sig')
        journals_string = journals_file.read()
        journals_list = [line.strip().lower() for line in journals_string.split('\n') if len(line.strip()) > 0]
        return journals_list

class ParsedJMP:
    '''
    Class that represents a parsed Job Market Paper.
    The PDF file should be only the first page of the JMP. The main method of
    jmp_title_parser makes sure that this is the case and also makes sure that
    the input PDF file is readable.
    For the priority sample, we have the name of the author. We will use that
    name.
    :param path: path of one PDF as argument.
    '''
    characters = []
    line_of_characters = []
    font_sizes = []
    title=''

    def __init__(self,path,jel_name,journals_list):

        #Set up pdfminer PageInterpreter
        rsrcmgr = PDFResourceManager()
        laparams = LAParams()
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        #Create PDF object
        fp = open(path, 'rb')
        parser = PDFParser(fp)
        document = PDFDocument(parser, password='')

        #Generate LTPage objects
        pages = PDFPage.create_pages(document)
        interpreter.process_page(next(pages))
        layout = device.get_result()
        fp.close()

        #Get a list of dictionaries with the text, font size, text of line and line number of every character.
        #Also get a list of lines from that list of character.
        self.char_properties_list = self.parse_font_sizes(layout._objs)
        self.line_properties_list = self.characters_to_lines(self.char_properties_list)

        #Find match between JEL names and the JMP.
        if jel_name[2]:
            self.authors_line, self.authors = self.match_names(self.line_properties_list,jel_name)
        else:
            self.authors_line = None
            self.authors = None

        #Find title with font size
        try:
            self.title, self.line_numbers_of_title = self.extract_title_from_font_sizes(self.char_properties_list, self.authors_line, journals_list)
        except Exception as e:
            print(e)
            self.title, self.line_numbers_of_title = '',set()

        #Find the name of the author(s) if we didn't find a match with JEL name.
        if not self.authors_line:
            try:
                self.authors = self.extract_author_names(self.line_properties_list,self.line_numbers_of_title)
            except Exception as e:
                print(e)
                self.authors =''

        fp.close()


    def parse_font_sizes(self, objs):
        '''
        Function that takes a list of LTPages and returns the size of the
        individual characters on the page
        '''
        alphanum_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        ascii_chars = '''0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c'''

        #initialize the result arrays with a null value to avoid exceptions for the first character parsed
        char_properties_list = [{'characters':'', 'line':'', 'line_number':0, 'font_size':0}]
        line_counter = -1
   #     counter = 1
        for obj in objs:
            if isinstance(obj, pdfminer.layout.LTTextBox):
                for o in obj._objs:
                    if isinstance(o,pdfminer.layout.LTTextLine):
   #                     counter+=1
                        line_counter += 1
                        text=o.get_text()
                        if text.strip():
                            for c in  o._objs:
                                char_properties = {'characters':None, 'line':None, 'line_number':None, 'font_size':None}
                                #replace by blank space where the character is not ascii (these often have weirdly high font sizes) or an accented letter
                                if isinstance(c, pdfminer.layout.LTChar) or isinstance(c, pdfminer.layout.LTAnno):
                                    char_properties['line'] = o.get_text()
                                    char_properties['line_number'] = line_counter

                                    #Replace by space if not ascii.
                                    if c.get_text() in ascii_chars:
                                        char_properties['characters'] = c.get_text()
                                    else:
                                        char_properties['characters'] = ''

                                    #Now for the exceptions. Different unicode characters that need to be handled specially.
                                    try:
                                        char_properties['characters'] = unaccent(c.get_text())
                                    except Exception:
                                        pass

                                    #Set font sizes. We want to avoid the large font sizes of special characters.
                                    if c.get_text() in alphanum_chars:
                                        char_properties['font_size'] = round(c.size,1)
                #                    elif c.get_text() == '\n':
                #                        char_properties['font_size'] = 0
                                    else:
                                        char_properties['font_size'] = char_properties_list[-1]['font_size']

        #                            if counter<6:
        #                                print(c.get_text().encode('utf-8'))
        #                                print(char_properties['font_size'])


                                char_properties_list.append(char_properties)
            # if it's a container, recurse
            elif isinstance(obj, pdfminer.layout.LTFigure):
                self.parse_font_sizes(obj._objs)

        #Return after removing the first cell added at initiation of list.
        return char_properties_list[1:]

    def characters_to_lines(self, char_properties_list):
        line_properties_list = [{'line':'', 'line_number':-1}]

        set_of_line_numbers = set([char_properties['line_number'] for char_properties in char_properties_list])

        for line_number in set_of_line_numbers:
            characters_in_title = [char_properties['characters'] for char_properties in char_properties_list if char_properties['line_number'] == line_number]
            line_text = ''.join(characters_in_title)
            dict_temp = {'line':line_text,'line_number':line_number}
            line_properties_list.append(dict_temp)

        return line_properties_list[1:]

    def match_names(self,line_properties_list,jel_name):
        '''
        Function that checks if the candidate name from the JEL list can be
        found in the JMP.
        Need to clean the JMP text and names in the same way before.
        Return the line number of author name and the coauthors found on the
        line.
        If we don't find a sufficient match return None.
        '''

        jel_name = [re.sub(r'[\.\']+', '', name) for name in jel_name]
        jel_name = [re.sub(r'[^a-zA-Z]+', ' ', name) for name in jel_name]
        jel_name = [re.sub(' +', ' ', name) for name in jel_name]
        jel_name = [line.lower().strip() for line in jel_name]

        for line_properties in line_properties_list:
            line_clean = re.sub(r'[\.\']+', '', line_properties['line'])
            line_clean = re.sub(r'[^a-zA-Z]+', ' ', line_clean)
            line_clean = re.sub(' +', ' ', line_clean)
            line_clean = line_clean.lower().strip()

            first_name_match = re.search(r'(?<![a-zA-Z0-9])'+jel_name[0]+r'(?![a-zA-Z0-9])',line_clean)
            last_name_match = re.search(r'(?<![a-zA-Z0-9])'+jel_name[2]+r'(?![a-zA-Z0-9])',line_clean)

            if first_name_match or last_name_match:
                authors = ''
                #tokenize for NER
                tokenized=word_tokenize(line_properties['line'].title())
                classified_text=st.tag(tokenized)
                #Concatenate the words recognized as names
                for token in classified_text:
                    if token[1] == 'PERSON':
                        authors += token[0] + ' '
                #Clean author names
                authors = re.sub(r'[\.\']+', '', authors)
                authors = re.sub(r'[^a-zA-Z\-:()&]+', ' ', authors)
                authors = re.sub(' +', ' ', authors)

                return line_properties['line_number'], authors.strip()

        return None, None

    def extract_title_from_font_sizes(self, char_properties_list, authors_line, journals_list):
        '''
        Function that takes lists with the PDF file's individual characters,
        the line of text of the individual characters, and the individual
        characters' font size and returns the title of the paper.
        '''

        #Get the max font size, but stop before the 'abstract' section (if we are lucky and it has an 'abstract' header) and skip author line.
        font_sizes_before_abstract = []
        line_with_abstract = 9999
        for char_properties in char_properties_list:
            if char_properties['line_number'] == authors_line:
                continue
            if char_properties['line'].lower().startswith('abstract') or char_properties['line'].lower().startswith('a b s t r a c t'):
                line_with_abstract = char_properties['line_number']
                break
            font_sizes_before_abstract.append(char_properties['font_size'])
        max_font_size = max(font_sizes_before_abstract)

        title=''
        line_numbers_of_title = set()
        line_counter = 0
        title_bool = False
        #Loop through characters and add them if they are max font-size.
        #If it hits max font size, and then hits smaller fonts, stop loop (title is over) to avoid hitting subtitles later.
        #Stop loop when entering the abstract section (it the jmp has one with the header 'abstract')
        for i,char_properties in enumerate(char_properties_list):
            if char_properties['line_number'] == line_with_abstract or (char_properties['line_number'] == authors_line and title_bool == True):
                break
            elif char_properties['line_number'] == authors_line and title_bool == False:
                continue
            if char_properties['font_size'] == max_font_size:

                line_numbers_of_title.add(char_properties['line_number'])
                title_bool = True
                #cap the number of lines the title can be on at 3
                if char_properties['characters'] == '\n':
                    line_counter += 1
                if line_counter == 4:
                    break
            elif char_properties['font_size'] != max_font_size and title_bool == True:
                break

        characters_in_title = [char_properties['characters'] for char_properties in char_properties_list if char_properties['line_number'] in line_numbers_of_title]
        title = ''.join(characters_in_title)

        #If the title ends with a stop word, we want to get the title on the next line.
        stopwords = (' and',' or',':',' if', ' in', ' by', ' every', ' a', ' an', ' each', ' for', ' from', ' the', ' it', ' not', ' on', ' if', ' at')
        if title.lower().strip().endswith(stopwords) and len(line_numbers_of_title)<3:
            line_numbers_of_title.add(max(line_numbers_of_title)+1)
            characters_in_title = [char_properties['characters'] for char_properties in char_properties_list if char_properties['line_number'] in line_numbers_of_title]
            title = ''.join(characters_in_title)

        #Clean title
        title = re.sub(r'[\.]+', '', title)
        title = re.sub(r'[^0-9a-zA-Z\-:%\'&]+', ' ', title)
        title = re.sub(r'&', r'and', title)
        title = re.sub(' +', ' ', title)
        title = title.strip()

        words_to_avoid = ['article in press',
                          'job market paper',
                          'working paper',
                          'nber',
                          'university',
                          'department',
                          'research',
                          'introduction',
                          'volume',
                          'january',
                          'february',
                          'march',
                          'april',
                          'may',
                          'june',
                          'july',
                          'august',
                          'september',
                          'october',
                          'november',
                          'december']

        journals_and_words_to_avoid = journals_list+words_to_avoid
        #If the title starts/ends with the headers to avoid or if it is too short, redo without the line where the "wrong" title was found.
        for to_avoid in journals_and_words_to_avoid:
            if title.lower().startswith(to_avoid):
                to_avoid_length = len(to_avoid)
                to_avoid_lines = set()
                title_counter = 0
                for char_properties in char_properties_list:
                    if char_properties['line_number'] >= min(line_numbers_of_title):
                        title_counter +=1
                    if title_counter > 0 and title_counter <= to_avoid_length:
                        to_avoid_lines.add(char_properties['line_number'])

                new_char_properties_list = [char_properties for char_properties in char_properties_list if char_properties['line_number'] not in to_avoid_lines]
                title, line_numbers_of_title = self.extract_title_from_font_sizes(new_char_properties_list,authors_line,journals_list)

            if title.lower().endswith(to_avoid):
                to_avoid_length = len(to_avoid)
                to_avoid_lines = set()
                title_counter = to_avoid_length
                for char_properties in char_properties_list[::-1]:
                    if char_properties['line_number'] <= max(line_numbers_of_title):
                        title_counter -= 1
                    if title_counter <= to_avoid_length and title_counter > 0:
                        to_avoid_lines.add(char_properties['line_number'])

                new_char_properties_list = [char_properties for char_properties in char_properties_list if char_properties['line_number'] not in to_avoid_lines]
                title, line_numbers_of_title = self.extract_title_from_font_sizes(new_char_properties_list,authors_line,journals_list)

        if len(title)<10:
            new_char_properties_list = [char_properties for char_properties in char_properties_list if char_properties['line_number'] not in line_numbers_of_title]
            title, line_numbers_of_title = self.extract_title_from_font_sizes(new_char_properties_list,authors_line,journals_list)

        return title, line_numbers_of_title

    def extract_author_names(self,line_properties_list, line_numbers_of_title):
        '''
        Function that takes as input a list of properties for each character
        of the first page of a JMP and returns the name of the first author.
        Stops after first match because that is all we need for cites search.
        Do not look for it in the lines of the title.
        '''

        author = ''

        #shortcut: first look in the first line after title
        try:
            line = line_properties_list[max(line_numbers_of_title)+1]['line']
            tokenized=word_tokenize(line)
            classified_text=st.tag(tokenized)
            for token in classified_text:
                if token[1] == 'PERSON':
                    author += token[0] + ' '
            if len(author)>1:
                author = re.sub(r'[^a-zA-Z\-:()\'&]+', ' ', author)
                author = re.sub(' +', ' ', author)
                return author.strip()
        except Exception:
            pass

        #then check all over the page, skipping the title
        for line_properties in line_properties_list:
            #Skip line if it is title line
            if line_properties['line_number'] in line_numbers_of_title:
                continue

            #Stop search if we reach the abstract
            if 'abstract' in line_properties['line'].lower():
                return ''

            tokenized=word_tokenize(line_properties['line'])
            classified_text=st.tag(tokenized)

            for token in classified_text:
                if token[1] == 'PERSON':
                    author += token[0] + ' '

            if len(author)>1:
                break

        #Clean author name
        author = re.sub(r'[\.\']+', '', author)
        author = re.sub(r'[^a-zA-Z\-:()&]+', ' ', author)
        author = re.sub(' +', ' ', author)

        return author.strip()


def main():
    '''Queries JMPs from SQL, and parses them one by one to extract the titles and authors'''
    #Import journal list
    journals_list = import_journals_list(r'.\journal_names.txt')

    ###Write query to retrieve JMPs from SQL
    query = ""

    format_strings = ','.join(['%s'] * len(cv_numbers))
    query = query % format_strings
    query = query % tuple(cv_numbers)
    query_df = sql_query_pandas(query)
    #Add name.
    query_df = query_df.join(df[['aid','fname','mname','lname']].set_index('aid'), how='left', on='aid').fillna('')

    results = []
    counter = 0
    num_rows = len(query_df.index)
    for index, row in query_df.iterrows():
        counter += 1
        start_time = time.time()

        #Remove the spaces from the filename
        filename = re.sub(r'[^A-Za-z0-9_\.]',r'',row['filename'])

        f = open(filename, 'wb')
        f.write(row['filecontent'])
        f.close()
        jel_name = [row['fname'],row['mname'],row['lname']]
        try:
            parsed_jmp = ParsedJMP(filename,jel_name,journals_list)
        except (pdfminer.pdfparser.PDFSyntaxError,pdfminer.psparser.PSEOF):
            continue
        os.remove(filename)

        result = [row['aid'],row['fname'],row['mname'],row['lname'],parsed_jmp.authors,parsed_jmp.title]
        results.append(result)
        print('Parsed JMP %d of %d (JMP %d). It took %d seconds.' %(counter,num_rows,row['aid'],time.time()-start_time))

    headers = ['aid','fname','mname','lname','authors','title']
    results_df=pd.DataFrame(results,columns=headers).sort_values(by='aid',axis=0).drop_duplicates(subset='aid',keep='last')
    results_df.to_excel(r'final_mergeFJ_missing_jmps.xlsx',index=False)

main()
