#pragma once
#include <cstdio>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

// Local research checkpoint, same binary/architecture only. The experiment
// runner additionally pins the binary and original BAL input by SHA-256.
class PrismReplayIO {
 public:
  FILE* file;
  bool reading;
  PrismReplayIO(const char* path, bool read) : file(std::fopen(path, read?"rb":"wb")), reading(read) {
    if(!file) throw std::runtime_error("cannot open replay checkpoint");
  }
  ~PrismReplayIO(){ if(file) std::fclose(file); }
  void bytes(void* p, size_t n){
    if((reading?std::fread(p,1,n,file):std::fwrite(p,1,n,file))!=n)
      throw std::runtime_error("incomplete replay checkpoint");
  }
  template<class T> void scalar(T& x){
    static_assert(std::is_trivially_copyable<T>::value,"checkpoint POD required");
    bytes(&x,sizeof x);
  }
  template<class T> void vector(std::vector<T>& v){
    size_t n=v.size(); scalar(n);
    if(n>10000000) throw std::runtime_error("invalid checkpoint vector size");
    if(reading) v.resize(n);
    bytes(v.data(),n*sizeof(T));
  }
  void expect(const std::string& expected){
    std::vector<char> actual(expected.begin(),expected.end()); vector(actual);
    if(std::string(actual.begin(),actual.end())!=expected)
      throw std::runtime_error("checkpoint version, dimensions or policy mismatch");
  }
};
