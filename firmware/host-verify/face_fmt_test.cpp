#include <cstdio>
#include <cassert>
// 复刻修复逻辑: 相机格式 → GrabForDetect 是否放行 + esp-dl pix_type 选择
#define V4L2_PIX_FMT_RGB565  0x50424752
#define V4L2_PIX_FMT_YUYV    0x56595559
#define V4L2_PIX_FMT_YUV422P 0x50323234
#define V4L2_PIX_FMT_RGB24   0x33424752
enum PixType { RGB565LE, YUYV, NONE };

bool grab_accepts(unsigned f){
    return f==V4L2_PIX_FMT_RGB565 || f==V4L2_PIX_FMT_YUV422P || f==V4L2_PIX_FMT_YUYV;
}
PixType pick(unsigned f){
    if(f==V4L2_PIX_FMT_YUYV || f==V4L2_PIX_FMT_YUV422P) return YUYV;
    return RGB565LE;
}
int main(){
    // 修复前的 bug: 相机实测输出 YUV422P/YUYV, 旧代码只认 RGB565 → 全拒 → 静默空转
    assert(grab_accepts(V4L2_PIX_FMT_YUV422P) && "YUV422P 必须放行(实测相机默认)");
    assert(grab_accepts(V4L2_PIX_FMT_YUYV)   && "YUYV 必须放行");
    assert(grab_accepts(V4L2_PIX_FMT_RGB565) && "RGB565 仍放行");
    assert(!grab_accepts(V4L2_PIX_FMT_RGB24) && "RGB24(3字节)不放行(buffer算法按2字节)");
    printf("[1] 格式放行: PASS\n");

    assert(pick(V4L2_PIX_FMT_YUYV)==YUYV);
    assert(pick(V4L2_PIX_FMT_YUV422P)==YUYV);
    assert(pick(V4L2_PIX_FMT_RGB565)==RGB565LE);
    printf("[2] pix_type 映射: PASS\n");
    printf("ALL PASS\n");
    return 0;
}
