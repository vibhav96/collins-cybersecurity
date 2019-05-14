#include <iostream>
#include <stdexcept>
#include <vector>
#include "NITFFile.h"

#define ACFTB__AC_MSN_ID__SZ  (20)
#define ACFTB__SENSOR_ID__SZ  (6)
#define IDATIM_DATE_SZ  (8)
#define MSTGTA__TGTLOC__SZ  (21)
#define MSTGTA_TGTLOC_LAT_SZ  (10)

NITFFile::NITFFile(std::string fileName)
{
  std::string errorId = "ERROR: ";
  std::string errorString;

  nitf_Error_init(&m_nitfError, "\0", "\0", 0, "\0", 0);
  m_nitfReader = nitf_Reader_construct(&m_nitfError);
  if(m_nitfReader != NULL) {
    m_nitfIOHandle = nitf_IOHandle_create(fileName.c_str(), NITF_ACCESS_READONLY, NITF_OPEN_EXISTING, &m_nitfError);
    if(!NITF_INVALID_HANDLE(m_nitfIOHandle)) {
      m_nitfRecord = nitf_Reader_read(m_nitfReader, m_nitfIOHandle, &m_nitfError);
    } else {
      errorString = errorId + "Returned invalid handle for " + fileName;
    }
  } else {
    errorString = errorId + "Could not initialize NITF Reader";
  }

  if(m_nitfRecord == NULL) {
    errorString = errorId + "Could not create NITF Record for " + fileName;
  }

  // Error condition found
  if(errorString.find(errorId) != std::string::npos) {
    if(m_nitfRecord != NULL) {
      nitf_Record_destruct(&m_nitfRecord);
      m_nitfRecord = NULL;
    }

    if(!NITF_INVALID_HANDLE(m_nitfIOHandle)) {
      nitf_IOHandle_close(m_nitfIOHandle);
    }
    
    if(m_nitfReader != NULL) {
      nitf_Reader_destruct(&m_nitfReader);
      m_nitfReader = NULL;
    }

    throw std::runtime_error(errorString);
  }
}

NITFFile::~NITFFile()
{
  if(m_nitfReader != NULL) {
    nitf_Reader_destruct(&m_nitfReader);
    m_nitfReader = NULL;
  }

  if(!NITF_INVALID_HANDLE(m_nitfIOHandle)) {
    nitf_IOHandle_close(m_nitfIOHandle);
  }

  if(m_nitfReader != NULL) {
    nitf_Reader_destruct(&m_nitfReader);
    m_nitfReader = NULL;
  }
}

nitf_Field* NITFFile::findTREField(std::string tag, std::string field, nitf_List* list)
{
  nitf_ListIterator current = nitf_List_begin(list);
  nitf_ListIterator last = nitf_List_end(list);
    
  while (nitf_ListIterator_notEqualTo(&current, &last)) {
    nitf_TRE* tre = (nitf_TRE*)nitf_ListIterator_get(&current);
    nitf_List* found = nitf_TRE_find(tre, field.c_str(), &m_nitfError);
    
    if (!found) {
      std::cout << "Failed to find TRE pattern " << field << std::endl;
      return NULL;     
    }
      
    nitf_ListIterator currentInst = nitf_List_begin(found);
    nitf_ListIterator lastInst = nitf_List_end(found);
    
    if (!nitf_ListIterator_notEqualTo(&currentInst, &lastInst)) {
      std::cout << "found the pattern but the list is empty?!" << std::endl; 
      return NULL;
    }

    while (nitf_ListIterator_notEqualTo(&currentInst, &lastInst)) {
      nitf_Pair* pair = (nitf_Pair*)nitf_ListIterator_get(&currentInst);
      nitf_Field* nitfField = (nitf_Field*)pair->data;

      if(field == pair->key) {
	/**
	 * This version will only find the first instance of the field
	 * we're looking for, which may not be the first sequentially since
	 * the search uses a random hash lookup. To find all instances of
	 * a TRE field, don't return on the next line. Instead, store all
	 * the fields and values we find and return an iterator to the list
	 * of matches.
	 **/
      
	return nitfField;
      }

      nitf_ListIterator_increment(&currentInst);
    }
  }

  return NULL;
}

nitf_Field* NITFFile::lookForTREField(std::string tag, std::string field) 
{
  nitf_Field *ret = NULL;
  std::vector<nitf_List *> list;

  // Look in the NITF File Header
  list.push_back(nitf_Extensions_getTREsByName(m_nitfRecord->header->userDefinedSection, tag.c_str()));
  list.push_back(nitf_Extensions_getTREsByName(m_nitfRecord->header->extendedSection, tag.c_str()));

  // Look in the NITF Image Subheaders
  nitf_ListIterator iter = nitf_List_begin(m_nitfRecord->images);
  nitf_ListIterator end = nitf_List_end(m_nitfRecord->images);
  while(nitf_ListIterator_notEqualTo(&iter, &end)) {
    nitf_ImageSegment *segment = (nitf_ImageSegment *)nitf_ListIterator_get(&iter);
    list.push_back(nitf_Extensions_getTREsByName(segment->subheader->userDefinedSection, tag.c_str()));
    list.push_back(nitf_Extensions_getTREsByName(segment->subheader->extendedSection, tag.c_str()));

    nitf_ListIterator_increment(&iter);
  }

  // Look in the NITF Data Extension Subheader
  iter = nitf_List_begin(m_nitfRecord->dataExtensions);
  end = nitf_List_end(m_nitfRecord->dataExtensions);
  while(nitf_ListIterator_notEqualTo(&iter, &end)) {
    nitf_DESegment *segment = (nitf_DESegment *)nitf_ListIterator_get(&iter);
    list.push_back(nitf_Extensions_getTREsByName(segment->subheader->userDefinedSection, tag.c_str()));
    nitf_ListIterator_increment(&iter);
  }

  std::vector<nitf_List *>::iterator it = list.begin();
  while(it != list.end()) {
    if((*it) != NULL) {
      ret = findTREField(tag, field, (*it));
      if(ret != NULL) {
	return ret;
      }
    }
    it++;
  }


  std::cout << "Could not find " << tag << ":" << field << std::endl;
  return NULL;
}

nitf_ImageSegment* NITFFile::getFirstImageSegment()
{
  nitf_ImageSegment *segment = NULL;
  
  nitf_ListIterator iter = nitf_List_begin(m_nitfRecord->images);
  nitf_ListIterator end = nitf_List_end(m_nitfRecord->images);
  if(nitf_ListIterator_notEqualTo(&iter, &end)) {
    segment = (nitf_ImageSegment *)nitf_ListIterator_get(&iter);
  }

  return segment;
}

std::string NITFFile::getDate()
{
  // From the First Image Subheader IDATIM field
  nitf_ImageSegment* segment = getFirstImageSegment();
  if(segment != NULL) {
    char chDateTime[NITF_IDATIM_SZ+1] = {0};
    NITF_BOOL ret = nitf_Field_get(segment->subheader->imageDateAndTime, chDateTime, NITF_CONV_STRING, NITF_IDATIM_SZ+1, &m_nitfError);
    if(ret == NITF_SUCCESS) {
      std::string date = chDateTime;
      date.resize(IDATIM_DATE_SZ);
      return date;
    }
  }
  return "UNKNOWN";
}

std::string NITFFile::getTime()
{
  // From the First Image Subheader IDATIM field
  nitf_ImageSegment* segment = getFirstImageSegment();
  if(segment != NULL) {
    char chDateTime[NITF_ISORCE_SZ+1] = {0};
    NITF_BOOL ret = nitf_Field_get(segment->subheader->imageDateAndTime, chDateTime, NITF_CONV_STRING, NITF_ISORCE_SZ+1, &m_nitfError);
    if(ret == NITF_SUCCESS) {
      std::string time = chDateTime;
      time = time.substr(IDATIM_DATE_SZ);
      return time;
    }
  }
  return "UNKNOWN";
}

std::string NITFFile::getMissionID()
{
  // From ACFTB:AC_MSN_ID
  nitf_Field *field = lookForTREField("ACFTB", "AC_MSN_ID");
  if(field != NULL) {
    char chMissionID[ACFTB__AC_MSN_ID__SZ+1] = {0};
    NITF_BOOL ret = nitf_Field_get(field, chMissionID, NITF_CONV_STRING, ACFTB__AC_MSN_ID__SZ+1, &m_nitfError);
    if(ret == NITF_SUCCESS) {
      return chMissionID;
    }
  }
  return "UNKNOWN";
}

std::string NITFFile::getClassification()
{
  // From the File Security in the NITF File Header
  char chClassification[NITF_FSCLAS_SZ+1] = {0};
  NITF_BOOL ret = nitf_Field_get(m_nitfRecord->header->classification, chClassification, NITF_CONV_STRING, NITF_FSCLAS_SZ+1, &m_nitfError);
  if(ret == NITF_SUCCESS) {
    std::string classification = chClassification;
    if(classification == "U") {
      classification = "UNCLASSIFIED";
    } else if(classification == "S") {
      classification = "SECRET";
    } else if(classification == "T") {
      classification = "TOP SECRET";
    } else if(classification == "R") {
      classification = "RESTRICTED";
    } else if(classification == "C") {
      classification = "CONFIDENTIAL";
    }

    return classification;
  }

  return "UNKNOWN";
}

bool NITFFile::getGeographicLocation(std::string &latitude, std::string &longitude)
{
  // From the MSTGTA Target Location
  nitf_Field *field = lookForTREField("MSTGTA", "TGTLOC");
  if(field != NULL) {
    char chTarget[MSTGTA__TGTLOC__SZ+1] = {0};
    NITF_BOOL ret = nitf_Field_get(field, chTarget, NITF_CONV_STRING, MSTGTA__TGTLOC__SZ+1, &m_nitfError);
    if(ret == NITF_SUCCESS) {
      latitude = chTarget;
      latitude.resize(MSTGTA_TGTLOC_LAT_SZ);
      
      longitude = chTarget;
      longitude = longitude.substr(MSTGTA_TGTLOC_LAT_SZ);

      return true;
    }
  }
  return false;
}

std::string NITFFile::getSensorType()
{
  // From the ACFTB Sensor ID field
  nitf_Field *field = lookForTREField("ACFTB", "SENSOR_ID");
  if(field != NULL) {
    char chSensorId[ACFTB__SENSOR_ID__SZ+1] = {0};
    NITF_BOOL ret = nitf_Field_get(field, chSensorId, NITF_CONV_STRING, ACFTB__SENSOR_ID__SZ+1, &m_nitfError);
    if(ret == NITF_SUCCESS) {
      return chSensorId;
    }
  }
  return "UNKNOWN";
}
