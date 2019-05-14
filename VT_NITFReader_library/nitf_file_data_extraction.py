import subprocess
from datetime import datetime
import psycopg2
import os

def read_file(file):
    #this function read the file and returns a list of all features from the file
    runNITFReader =  subprocess.Popen("./runNITFReader.sh " + file, shell=True, stdout=subprocess.PIPE).stdout
    features =  runNITFReader.read()
    features_list = features.split() #this splits the output of the runNITFReader script into a list
    print features
    return features_list

def extract_features(features_list):
    #this function extracts values of all the features from the feature list and returns a dict
    features_dict  = {}
    date_found = False
    time_found = False
    missionid_found = False
    classification_found = False
    geographiclocation_found = False
    senesortype_found = False


    geographiclocation_type = ""

    #this for loop finds the classification_type of the file to automatically populate the correct table
    for elements in features_list:

        #THIS SET OF if-elif STATEMENTS FIND VALUE FOR THE ELEMENTS
        if date_found == True and elements != "=": #this if loop jumps skips "=" in the list
            features_dict["Date"] = datetime.utcfromtimestamp(int(elements)).strftime('%Y-%m-%d')
            date_found = False
            #print "Date found", date_type

        elif time_found == True and elements != "=": #this if loop jumps skips "=" in the list
            features_dict["Time"] = datetime.utcfromtimestamp(int(elements)).strftime('%H:%M:%S')
            time_found = False
            #print "Time found", time_type

        elif missionid_found == True and elements != "=": #this if loop jumps skips "=" in the list
            features_dict["MissionID"] = elements
            missionid_found = False
            #print "MissionID found", missionid_type

        elif classification_found == True and elements != "=": #this if loop jumps skips "=" in the list
            features_dict["Classificaiton"] = elements
            classification_found = False
            #print "Classification found", classification_type

        elif geographiclocation_found == True and elements != "=" and elements != "Locaiton": #this if loop jumps skips "=" in the list
            if elements == "Sensor":
                geographiclocation_found = False
                features_dict["Geographic Locaiton"] = geographiclocation_type
                #print "Geographic Location found", geographiclocation_type
            else:
                geographiclocation_type = str(geographiclocation_type)+elements


        elif senesortype_found == True and elements != "=" and elements != "Type": #this if loop jumps skips "=" in the list
            features_dict["Sensor Type"] = elements
            senesortype_found = False
            #print "sensor Type found", senesortype_type

        #THIS SET OF if-elif STATEMENTS FIND ELEMENTS
        if elements == "Date":
            date_found = True

        elif elements == "Time":
            time_found = True

        elif elements == "MissionID":
            missionid_found = True

        elif elements == "Classification":
            classification_found = True

        elif elements == "Geographic": #short for "Geographic Location"
            geographiclocation_found = True

        elif elements == "Sensor": #short for "Sensor Type"
            senesortype_found = True
    #print features
    return features_dict

def insert_features(features_dict):
        connection = psycopg2.connect(user = "fieldservice",
                                              password = "fieldservice",
                                              host = "127.0.0.1",
                                              port = "5432",
                                              database = "postgres")

        cursor = connection.cursor()

        if features_dict["Classificaiton"] == "UNCLASSIFIED" or features_dict["Classification"] == "UNCLASSIFIED":
            insert_query = """INSERT INTO unclass (date_, time_, missionID, classification, location, sensortype )VALUES
            (%s,%s,%s,%s,%s,%s)"""
            values_to_enter = (features_dict['Date'],features_dict['Time'],features_dict['MissionID'],features_dict['Classificaiton'],features_dict['Geographic Locaiton'],features_dict['Sensor Type'])
            cursor.execute(insert_query,values_to_enter)
            connection.commit()

        elif features_dict["Classificaiton"] == "SECRET" or features_dict["Classification"] == "SECRET":
            insert_query = """INSERT INTO secret (date_, time_, missionID, classification, location, sensortype)VALUES
            (%s,%s,%s,%s,%s,%s)"""
            values_to_enter = (features_dict['Date'],features_dict['Time'],features_dict['MissionID'],features_dict['Classificaiton'],features_dict['Geographic Locaiton'],features_dict['Sensor Type'])
            cursor.execute(insert_query,values_to_enter)
            connection.commit()

        elif features_dict["Classificaiton"] == "TOPSECRET" or features_dict["Classification"] == "TOPSECRET":
            insert_query = """INSERT INTO topsecret (date_, time_ , missionID, classification, location, sensortype) VALUES
            (%s,%s,%s,%s,%s,%s)"""
            values_to_enter = (features_dict['Date'],features_dict['Time'],features_dict['MissionID'],features_dict['Classificaiton'],features_dict['Geographic Locaiton'],features_dict['Sensor Type'])
            cursor.execute(insert_query,values_to_enter)
            connection.commit()

def main():

    #iterating through all the files
    for file in os.listdir("/vagrant/VT_NITFReader_library"):
        if file.endswith(".ntf"): #validating file name
            #print file
            if file == "FNov15.VERT HIG.EO.432.0000.ntf":
                pass
            else:
                features_list = read_file(file)
                features_dict = extract_features(features_list)
                insert_features(features_dict)
            break






if __name__ == "__main__":
    main()
