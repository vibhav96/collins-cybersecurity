#include <iostream>
#include <string>
#include <stdexcept>
#include "NITFFile.h"

int main(int argc, char **argv)
{
  std::string fileName;

  std::cout << "Starting..." << std::endl;

  int nArgs = 0;
  std::string arg;
  while(nArgs < argc) {
    arg = argv[nArgs];

    if(arg == "-file") {
      nArgs++;
      if(nArgs < argc) {
	fileName = argv[nArgs];
      }
    }

    nArgs++;
  }

  std::cout << "Attepmpting to read " << fileName << std::endl;

  try {
    if(fileName.length() > 0) {
      NITFFile nitfFile(fileName);

      std::string date = "UNKNOWN";
      std::string time = "UNKNOWN";
      std::string mission = "UNKNOWN";
      std::string classification = "UNKNOWN";
      std::string latitude = "UNKNOWN";
      std::string longitude = "UNKNOWN";
      std::string sensorType = "UNKNOWN";

      date = nitfFile.getDate();
      time = nitfFile.getTime();
      mission = nitfFile.getMissionID();
      classification = nitfFile.getClassification();
      bool bGeoRet = nitfFile.getGeographicLocation(latitude, longitude);
      sensorType = nitfFile.getSensorType();

      std::cout << "Date = " << date << std::endl;
      std::cout << "Time = " << time << std::endl;
      std::cout << "MissionID = " << mission << std::endl;
      std::cout << "Classification = " << classification << std::endl;
      std::cout << "Geographic Locaiton = (" << latitude << ", " << longitude << "), " << bGeoRet << std::endl;
      std::cout << "Sensor Type = " << sensorType << std::endl;
    }
    else {
      std::cout << "No NITF file specified" << std::endl;
    }
  }
  catch(std::runtime_error e)
  {
    std::cerr << e.what() << std::endl;
  }
  catch(...) {
    std::cerr << "Caught an unknown error" << std::endl;
  }

  std::cout << "Completed processing " << fileName << std::endl;

  return 0;
}
