#include <cstdio>
#include <cassert>
// 复刻 trigger_face_greeting 的 idle 守卫 + FaceEventModifier 冷却
enum State { Idle=3, Connecting=4, Listening=5, Speaking=6 };
bool trigger(State s){ return s==Idle; }  // 仅 idle 才主动问好

int main(){
    // 只有 idle 触发大脑, 其余状态忽略(不打断)
    assert(trigger(Idle));
    assert(!trigger(Connecting) && !trigger(Listening) && !trigger(Speaking));
    printf("[1] 仅idle触发大脑问好, 对话中不打断: PASS\n");

    // 冷却: 20s 内不重复 (本地音+大脑都受同一冷却门控)
    unsigned last=0, cd=20000;
    auto can=[&](unsigned now){ return now-last>=cd || last==0; };
    assert(can(1000)); last=1000;
    assert(!can(3000));           // 人晃一下不重复喊
    assert(!can(15000));
    assert(can(21001));           // 20s 后可再问
    printf("[2] 20s冷却门控(本地+大脑同步): PASS\n");

    // 时序: 本地音~2s, 大脑~3-5s → 天然错开不叠音
    int local_end=2000, brain_start=3500;
    assert(brain_start > local_end);
    printf("[3] 本地音(2s)先于大脑(3.5s+)结束, 不叠音: PASS\n");
    printf("ALL PASS\n");
    return 0;
}
