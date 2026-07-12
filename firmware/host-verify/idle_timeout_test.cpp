#include <cstdio>
#include <cassert>
// 复刻 application.cc 的空闲超时状态机逻辑, 验证边界
enum State { Idle=3, Connecting=4, Listening=5, Speaking=6 };
static constexpr int kTimeout = 30;

struct Sim {
    int listening_idle_ticks_ = 0;
    State state = Listening;
    bool voice = false;
    bool went_idle = false;

    void on_state_change(State s){ state=s; listening_idle_ticks_=0; }
    void on_vad(bool speaking){ if(state==Listening && speaking) listening_idle_ticks_=0; voice=speaking; }
    void on_tick(){
        if(state==Listening && !voice){
            if(++listening_idle_ticks_ >= kTimeout){
                listening_idle_ticks_=0;
                went_idle=true;
                on_state_change(Idle);
            }
        } else {
            listening_idle_ticks_=0;
        }
    }
};

int main(){
    // 场景1: listening 静默 30s → 回 idle
    { Sim s; s.on_state_change(Listening);
      for(int i=0;i<29;i++){ s.on_tick(); assert(!s.went_idle); }
      s.on_tick(); assert(s.went_idle && s.state==Idle);
      printf("[1] 静默30s回idle: PASS\n"); }

    // 场景2: 中途说话清零, 不误触发
    { Sim s; s.on_state_change(Listening);
      for(int i=0;i<25;i++) s.on_tick();
      s.on_vad(true);              // 大哥开口
      assert(s.listening_idle_ticks_==0);
      s.on_vad(false);             // 说完
      for(int i=0;i<29;i++){ s.on_tick(); assert(!s.went_idle); }
      s.on_tick(); assert(s.went_idle);
      printf("[2] 中途说话清零重新计时: PASS\n"); }

    // 场景3: Speaking 态不计时 (TTS 播放中不该超时)
    { Sim s; s.on_state_change(Speaking);
      for(int i=0;i<100;i++){ s.on_tick(); assert(!s.went_idle); }
      printf("[3] Speaking态不超时: PASS\n"); }

    // 场景4: 持续说话(voice=true)不超时
    { Sim s; s.on_state_change(Listening); s.on_vad(true);
      for(int i=0;i<100;i++){ s.on_tick(); assert(!s.went_idle); }
      printf("[4] 持续说话不超时: PASS\n"); }

    // 场景5: 回idle后不再计时 (幂等, 不重复触发)
    { Sim s; s.on_state_change(Listening);
      for(int i=0;i<30;i++) s.on_tick();
      assert(s.state==Idle); s.went_idle=false;
      for(int i=0;i<100;i++){ s.on_tick(); assert(!s.went_idle); }
      printf("[5] 回idle后不再触发: PASS\n"); }

    printf("ALL PASS\n");
    return 0;
}
