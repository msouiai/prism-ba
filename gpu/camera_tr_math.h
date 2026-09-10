#pragma once
#include <algorithm>
#include <cmath>
namespace prism_camera_tr {
inline double scale(double norm,double radius){return norm>radius?radius/norm:1.;}
inline double prediction(double bd,double curvature,double a){return a*bd-.5*a*a*curvature;}
inline bool accept(double actual,double predicted,double norm,double radius){
 return std::isfinite(actual)&&std::isfinite(predicted)&&predicted>0&&actual>0&&
        actual/predicted>=.1&&std::isfinite(norm)&&norm<=radius*(1+1e-8);
}
inline double radius_after(double radius,double norm,double rho){
 if(!std::isfinite(rho)||rho<.25)return std::max(1e-14,.25*radius);
 if(rho>.75&&norm>=.8*radius)return std::min(1e16,2*radius);
 return radius;
}
}
