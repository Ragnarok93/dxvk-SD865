
#include <atomic>
#include <cstdint>
#include <iostream>
#include <string>
#include <sstream>
#include "util_ff7r_timing.h"
using dxvk::Ff7rTimingCounter;
namespace env { std::string value; std::string getEnvVar(const char*) {return value;} }
struct Logger { static void info(const std::string& value) { std::cout << value; std::cout << "\n"; } };
namespace vk { inline uint64_t getObjectHandle(uint64_t value) { return value; } }
constexpr uint64_t VK_NULL_HANDLE=0;
struct VkRenderingAttachmentInfo {uint64_t imageView; int imageLayout,loadOp,storeOp,resolveMode; uint64_t resolveImageView; int resolveImageLayout;};
struct VkRenderingInfo { struct {struct {int x,y;} offset; struct {uint32_t width,height;} extent;} renderArea;
uint32_t layerCount, viewMask, flags, colorAttachmentCount;
const VkRenderingAttachmentInfo *pColorAttachments,*pDepthAttachment,*pStencilAttachment;};
struct Dispatch {int calls=0; const VkRenderingInfo* seen=nullptr; void vkCmdBeginRendering(int,const VkRenderingInfo* p) {calls++;seen=p;}};
struct Wrapper {Dispatch *m_vkd; struct {bool execCommands=false;} m_cmd; int getCmdBuffer(){return 1;}
METHOD
};
int main(int argc,char** argv) {
  env::value=argc>1?argv[1]:"0";
  VkRenderingAttachmentInfo color[2]={{1,2,0,0,1,3,2},{0,2,2,1,0,0,0}};
  VkRenderingAttachmentInfo depth={4,5,1,0,0,0,0};
  VkRenderingInfo info={{{0,0},{1280,720}},1,0,2,2,color,&depth,&depth};
  Dispatch d; Wrapper w{&d, {false}}; w.cmdBeginRendering(&info);
  if(d.calls!=1 || d.seen!=&info || !w.m_cmd.execCommands || color[0].storeOp!=0) return 9;
  std::cout << "dispatch_calls=" << d.calls << " state_unchanged=1\n";
}
