# -*- coding: utf-8 -*-
"""
Created on Thu Oct 24 14:43:52 2019

@author: julesboud

Requires the scholarly package from https://github.com/OrganicIrradiation/scholarly.
"""
import requests, json, re, unidecode
import scholarly
from importexportcsv import ImportCSV, ExportCSV
from difflib import SequenceMatcher
from collections import OrderedDict

def similarity(s1,s2):
    '''
    Uses Microsoft Academic training data to give a measure of how two academic
    strings are similar.
    Need
    '''
    prop_defaults = {
            #Default properties for both interpret and evaluate
            'url' : "https://api.labs.cognitive.microsoft.com/academic/v1.0/",
            'password' : "" ##input subscription key,
            'model' : "&model=latest",
            'count' : "&count=1",
            'offset' : "&offset=0",
            #Default properties for only interpret
            'complete' : "&complete=1",
            'timeout' : "&timeout=100000",
            #Default properties for only interpret
            'attributes' : "&attributes=Ti,Y,CC,AA.AuN,J.JN"
    }

    res_sim = requests.get(prop_defaults['url']+'similarity?'+'s1='+s1+'&s2='+s2+prop_defaults['password'])
    data=json.loads(res_sim.content)
    return data

def get_citations(first_name,middle_name,last_name,title,authors):
    if not title:
        return '','','',''

    queries = set()
    if authors:
        queries.add(' '.join([authors,title]))
    if middle_name:
        queries.add(' '.join([first_name,middle_name,last_name,title]))
    queries.add(' '.join([first_name,last_name,title]))

    for query in queries:
        print(query)

        #If a ConnectionRefusedError is thrown it will get put back in the set of titles to run (see main method)
        search_query = scholarly.search_pubs_query(query)
        query_result = next(search_query)

        print(query_result)

        result_title = query_result.bib['title']
        result_year = query_result.bib['year']
        result_number_of_authors = len(query_result.bib['author'].split('and'))
        try:
            result_citations = query_result.citedby
        except AttributeError:
            result_citations = 0

        #First, if we have the JEL name, check if the JEL name is in there. If not, continue.
        #If we have a parsed list of authors check that the name of one of the parsed authors is in the GS results.
        jel_bool = last_name and unidecode.unidecode(last_name).lower() in unidecode.unidecode(query_result.bib['author']).lower()
        print(not jel_bool)
        parsed_authors_bool = [i for i in re.sub(r' and ',' ',authors).split(' ') if i in re.sub(r' and ',' ',query_result.bib['author']).split(' ') and len(i)>1]
        print(not parsed_authors_bool)
        if not jel_bool and not parsed_authors_bool:
            continue

        #If the title has a close academic meaning, looks similar to, or starts with 'essay', return.
        mak_similarity_score = similarity(title,result_title)
        if isinstance(mak_similarity_score,dict):         #If we get an error from the MAK AI, just throw an error and retry.
            raise StopIteration
        difflib_similarity_score = SequenceMatcher(None,
                                                   re.sub(r'\s+',' ',re.sub(r'[^A-Za-z0-9 ]+', ' ', title)).lower(),
                                                   re.sub(r'\s+',' ',re.sub(r'[^A-Za-z0-9 ]+', ' ', result_title)).lower()).ratio()

        if difflib_similarity_score > 0.9 or mak_similarity_score > 0.8 or re.match(r'essay',result_title.lower()):
            return result_title, result_year, result_number_of_authors, result_citations


    return '','','',''

def main(filename):
    csv_in=ImportCSV(filename, errors_handling = 'ignore')
    list_of_dict = csv_in.read_csv()
    #Tranform it into hashable list and then put into set. Add an element at the end for the counter.
    set_of_tuple = set([tuple(ordered.values())+tuple([0]) for ordered in list_of_dict])
    keys = tuple(list_of_dict[0].keys())+tuple(['Counter'])
    print("%d JMPs identified \n" %len(list_of_dict))

    csv_out=ExportCSV(fileName=filename.split('.')[0]+'_citations_gs.csv', headers=['aid','JEL First Name','JEL Middle Name','JEL Last Name','Authors','Title','Title GS','Year of publication','Number of Authors','Citations'], resetFile=True)
    while set_of_tuple:
        info_list = set_of_tuple.pop()
        #Transform back from list to dict.
        info_dict = OrderedDict(zip(keys, info_list))

        try:
            info_dict['Counter'] = info_dict['Counter']+1
            info_dict['Title GS'], info_dict['Number of Authors'], info_dict['Year of Publication'], info_dict['Citations'] = get_citations(info_dict['JEL First Name'],info_dict['JEL Middle Name'],info_dict['JEL Last Name'],info_dict['Title'],info_dict['Authors'])
        except (ConnectionRefusedError,StopIteration) as e:
            print(e)
            #If we have tried less than 10 times, try again. Else return empty values.
            if info_dict['Counter'] <= 10:
                set_of_tuple.add(tuple(info_dict.values()))
                continue
            else:
                info_dict['Title GS'], info_dict['Number of Authors'], info_dict['Year of Publication'], info_dict['Citations'] = '','','',''

        del info_dict['Counter']
        csv_out.write_csv(info_dict)

main(r'final_mergeFJ_missing_jmps_no_match_1_corrected.csv')
