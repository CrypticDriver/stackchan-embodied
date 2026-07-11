#include <cstdint>
#include <cstdio>
#include <cmath>
static uint32_t g_ms=0;
#include "md_real.inc"
void feed(MotionDetector&d,float x,float y,float z,int ms){d.update(x,y,z);g_ms+=ms;}
int main(){
    int f,p,s;
    MotionDetector d;f=p=s=0;
    for(int i=0;i<20;i++){feed(d,0.1,0.1,9.8,100);if(d.isFlipDetected())f++;if(d.isPickUpDetected())p++;if(d.isShakeDetected())s++;}
    printf("静置: flip=%d pick=%d shake=%d (期望 0 0 0)\n",f,p,s);
    f=0; for(int i=0;i<3;i++)feed(d,0.1,0.1,9.8,100); feed(d,3,3,0,100);feed(d,3,3,-5,100);
    for(int i=0;i<10;i++){feed(d,0.1,0.1,-9.8,100);if(d.isFlipDetected())f++;}
    printf("倒扣: flip=%d (期望 1)\n",f);
    f=0; for(int i=0;i<5;i++)feed(d,0.1,0.1,9.8,100);
    for(int i=0;i<8;i++){feed(d,0.1,0.1,-9.8,100);if(d.isFlipDetected())f++;}
    printf("二次倒扣: flip=%d (期望 1)\n",f);
    MotionDetector d2;p=0;
    for(int i=0;i<10;i++)feed(d2,0.1,0.1,9.8,100);
    feed(d2,0.5,0.5,15.5,100);if(d2.isPickUpDetected())p++;
    for(int i=0;i<4;i++){feed(d2,0.3,0.3,10.2,100);if(d2.isPickUpDetected())p++;}
    printf("拿起: pick=%d (期望 1)\n",p);
    MotionDetector d3;f=p=s=0;
    for(int i=0;i<15;i++){feed(d3,15*(i%2?1:-1),2,9.8,80);if(d3.isFlipDetected())f++;if(d3.isPickUpDetected())p++;if(d3.isShakeDetected())s++;}
    printf("晃动: shake=%d flip=%d pick=%d (期望 s>=1 f=0 p=0)\n",s,f,p);
    MotionDetector d4;p=0;
    for(int i=0;i<8;i++)feed(d4,0.1,0.1,9.8,100);
    feed(d4,0.5,0.5,15.5,100);if(d4.isPickUpDetected())p++;
    for(int i=0;i<3;i++){feed(d4,0.3,0.3,10.2,100);if(d4.isPickUpDetected())p++;}
    for(int i=0;i<8;i++){feed(d4,0.1,0.1,9.8,100);if(d4.isPickUpDetected())p++;}
    printf("拿起+放回: pick=%d (期望 1, 放回不重复)\n",p);
    return 0;
}
