#include <string>
#include <deque>
#include "import/nitf.h"


class NITFFile
{
 public:
  NITFFile(std::string fileName);
  ~NITFFile();

  std::string getDate();
  std::string getTime();
  std::string getMissionID();
  std::string getClassification();
  bool getGeographicLocation(std::string &latitude, std::string &longitude);
  std::string getSensorType();

 private:
  nitf_Field* lookForTREField(std::string tag, std::string field);
  nitf_Field* findTREField(std::string tag, std::string field, nitf_List* list);
  nitf_ImageSegment* getFirstImageSegment();

  nitf_Error m_nitfError;
  nitf_Reader *m_nitfReader;
  nitf_IOHandle m_nitfIOHandle;
  nitf_Record *m_nitfRecord;
};
