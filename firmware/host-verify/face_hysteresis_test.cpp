#include <cstdio>
#include <cassert>
// 复刻检测任务的强滞后状态机: 验证"坐着不动闪帧"不会反复触发 Appear
static const int APPEAR_HITS=2, GONE_MISSES=80;
struct Det {
    bool present=false; int hit=0, miss=0; int appear_count=0, gone_count=0;
    void frame(bool seen){
        if(seen){ hit++; miss=0; } else { miss++; hit=0; }
        if(!present && hit>=APPEAR_HITS){ present=true; appear_count++; }
        else if(present && miss>=GONE_MISSES){ present=false; gone_count++; }
    }
};
int main(){
    // 场景1: 大哥来了坐下, 中间偶尔漏帧(坐着不动闪烁), 全程只 Appear 一次
    { Det d; 
      for(int i=0;i<2;i++) d.frame(true);              // 来了→Appear
      // 坐 10 分钟(1200帧): 大多有脸, 每 ~10 帧漏 1 帧
      for(int i=0;i<1200;i++) d.frame(i%10!=0);
      assert(d.appear_count==1 && d.gone_count==0);
      printf("[1] 坐10min偶尔漏帧: Appear=%d Gone=%d (只招呼1次): PASS\n",d.appear_count,d.gone_count); }

    // 场景2: 连续漏帧但<40s (79帧) 不算走
    { Det d; for(int i=0;i<2;i++) d.frame(true);
      for(int i=0;i<79;i++) d.frame(false);            // 39.5s 没脸
      assert(d.present && d.gone_count==0);
      d.frame(false);                                  // 第80帧=40s → Gone
      assert(!d.present && d.gone_count==1);
      printf("[2] 连续没脸 79帧不走, 80帧才走: PASS\n"); }

    // 场景3: 真的离开够久再回来 → 才第二次 Appear
    { Det d; for(int i=0;i<2;i++) d.frame(true);        // 第一次来
      for(int i=0;i<80;i++) d.frame(false);            // 真离开40s→Gone
      for(int i=0;i<2;i++) d.frame(true);              // 回来→第二次Appear
      assert(d.appear_count==2 && d.gone_count==1);
      printf("[3] 真离开40s再回来才二次招呼: PASS\n"); }

    // 场景4: 单帧误检不触发(APPEAR_HITS=2)
    { Det d; d.frame(true); d.frame(false);
      assert(d.appear_count==0);
      printf("[4] 单帧误检不招呼: PASS\n"); }
    printf("ALL PASS\n"); return 0;
}
