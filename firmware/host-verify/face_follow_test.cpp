#include <cstdio>
#include <cassert>
// 复刻 hal_face_detect 坐标映射 + face_event 平滑/冷却逻辑
int face_x_from_box(int lu,int rd,int w){
    int cx=(lu+rd)/2;
    int fx = -(cx*200/(w>0?w:1)-100);   // 镜像
    if(fx<-100)fx=-100; else if(fx>100)fx=100;
    return fx;
}
int main(){
    int W=320;
    // 脸在画面正中 → 眼看正中(0)
    assert(face_x_from_box(140,180,W)==0);
    printf("[1] 居中→0: PASS\n");
    // 脸在画面右侧(cx≈280) → 镜像后眼往左看(负)? 检查方向
    int right = face_x_from_box(260,300,W);  // cx=280 → raw=280*200/320-100=75 → 取负=-75
    assert(right==-75); printf("[2] 画面右(cx280)→x=%d (镜像): PASS\n",right);
    // 脸在画面左(cx≈40) → +75
    int left = face_x_from_box(20,60,W);     // cx=40 → 40*200/320-100=-75 → 取负=+75
    assert(left==75); printf("[3] 画面左(cx40)→x=%d: PASS\n",left);
    // 边界 clip
    assert(face_x_from_box(0,0,W)==100 && face_x_from_box(319,319,W)<=100);
    printf("[4] 边界clip: PASS\n");

    // 平滑逼近: eye 每帧走 1/3, 数帧后收敛到目标
    int eye=0, target=90;
    for(int i=0;i<20;i++) eye += (target-eye)/3;
    assert(eye>=85 && eye<=90); printf("[5] 平滑逼近收敛到%d: PASS\n",eye);

    // 冷却: 20s 内不重复问好
    unsigned last=0, cd=20000;
    auto can_greet=[&](unsigned now){ return now-last>=cd || last==0; };
    assert(can_greet(1000)); last=1000;      // 首次可
    assert(!can_greet(5000));                // 4s后不可
    assert(can_greet(21001));                // 20s后可
    printf("[6] 问好冷却20s: PASS\n");
    printf("ALL PASS\n");
    return 0;
}
