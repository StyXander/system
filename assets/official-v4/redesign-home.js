
(()=>{'use strict';
const home=document.getElementById('redesign-home');
home.querySelectorById=id=>home.querySelector('#'+id);
/* ============================================================
   审迹智链 · 雾面灰金属装置版
   Canvas 伪 3D 引擎：双侧独立锚定、独立旋转、动态光照、
   深度排序（含体积烟雾）、纸张厚度与翻页、分阶段入场。
   ============================================================ */
const canvas=home.querySelectorById('world'),stage=home.querySelectorById('stage');
const layers={background:canvas,a:home.querySelectorById('world-left'),b:home.querySelectorById('world-right')};
const contexts=Object.fromEntries(Object.entries(layers).map(([key,layer])=>[key,layer.getContext('2d',{alpha:true})]));
let ctx=contexts.background;
const cursorEl=home.querySelectorById('cursor');
const prefersReduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let w=1400,h=880,dpr=1,animationOn=true,rasterRevision=0;
function resize(){const r=canvas.getBoundingClientRect();const RW=Math.max(240,r.width||window.innerWidth),RH=Math.max(240,r.height||window.innerHeight);w=RW;h=RH;dpr=Math.min(devicePixelRatio||1,1.8);for(const [key,layer] of Object.entries(layers)){layer.width=Math.round(w*dpr);layer.height=Math.round(h*dpr);contexts[key].setTransform(dpr,0,0,dpr,0,0);}rasterRevision++;}
resize();
requestAnimationFrame(resize);
setTimeout(resize,100);setTimeout(resize,600);
window.addEventListener('resize',resize);
if(typeof ResizeObserver!=='undefined'){const ro=new ResizeObserver(()=>resize());ro.observe(canvas);ro.observe(stage)}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const mix=(a,b,k)=>a+(b-a)*k;
const easeOut=k=>1-Math.pow(1-k,3);
const V=(x,y,z)=>({x,y,z});

/* ---------------- 状态 ---------------- */
const MAXD=300,MAXP=120;
const state={active:'a',dragging:null};

/* ---------------- 材质与光照 ---------------- */
const MAT={
  paper:'#F4F1EC',mist:'#E7E5E0',mistD:'#D8D5D0',silver:'#B8B5AF',silverD:'#8F8C87',silverDD:'#5E5C59',
  graphite:'#2B2B2B',ink:'#1B1B1B',copper:'#A45549',copperD:'#7E3F35',white:'#FBFAF7'
};
const LIGHT=(()=>{const v={x:-.36,y:.56,z:.75},n=Math.hypot(v.x,v.y,v.z);return{x:v.x/n,y:v.y/n,z:v.z/n}})();
const RGB={};
function toRGB(hex){let c=RGB[hex];if(c)return c;const s=hex.replace('#','');c=[parseInt(s.slice(0,2),16),parseInt(s.slice(2,4),16),parseInt(s.slice(4,6),16)];RGB[hex]=c;return c}
function shade(hex,k){const c=toRGB(hex);const v=q=>Math.round(clamp(q*k,0,255));return 'rgb('+v(c[0])+','+v(c[1])+','+v(c[2])+')'}
/* 面法线 → 相机空间光照系数 */
function rotN(G,nx,ny,nz){
  const cy=Math.cos(G.yaw),sy=Math.sin(G.yaw);
  const x1=nx*cy+nz*sy,z1=-nx*sy+nz*cy;
  const cp=Math.cos(G.pitch),sp=Math.sin(G.pitch);
  const y1=ny*cp-z1*sp,z2=ny*sp+z1*cp;
  return{x:x1,y:y1,z:z2};
}
function litK(G,f){
  const n=rotN(G,f.nx,f.ny,f.nz);
  const d=n.x*LIGHT.x+n.y*LIGHT.y+n.z*LIGHT.z;
  return .42+.70*Math.max(0,d);
}
/* 细线颜色：亮面用深线、暗面用浅线 —— 保证棱线始终清晰 */
function edgeOf(k){return k>.88?'rgba(30,30,30,.34)':'rgba(244,241,236,.34)'}

/* ---------------- 分组 ---------------- */
const GROUPS={
  a:{id:'a',dragX:0,dragY:0,velX:0,velY:0,faces:[],smoke:null,baseYaw:-.48,basePitch:.42,yaw:-.48,pitch:.42,spin:1,zoom:1,zoomT:1,alpha:1,alphaT:1,sx:0,sy:0,focal:640,dist:16,breath:0,reveal:0,revealT:0},
  b:{id:'b',dragX:0,dragY:0,velX:0,velY:0,faces:[],smoke:[],baseYaw:.5,basePitch:.42,yaw:.5,pitch:.42,spin:.64,zoom:1,zoomT:1,alpha:1,alphaT:1,sx:0,sy:0,focal:640,dist:16,breath:2.4,reveal:0,revealT:0}
};
function face(G,pts,c,nx,ny,nz,opt){
  opt=opt||{};
  G.faces.push({p:pts,c,nx,ny,nz,metal:!!opt.metal,draw:opt.draw||null,flip:opt.flip||null,alpha:opt.alpha==null?1:opt.alpha,noEdge:!!opt.noEdge});
}
/* 立体盒：6 面 + 法线 */
function box(G,x,y,z,ww,hh,dd,color,opt){
  opt=opt||{};
  const hw=ww/2,hh2=hh/2,hd=dd/2;
  const A=V(x-hw,y-hh2,z-hd),B=V(x+hw,y-hh2,z-hd),C=V(x+hw,y+hh2,z-hd),D=V(x-hw,y+hh2,z-hd);
  const E=V(x-hw,y-hh2,z+hd),F=V(x+hw,y-hh2,z+hd),Gp=V(x+hw,y+hh2,z+hd),I=V(x-hw,y+hh2,z+hd);
  face(G,[E,F,Gp,I],color,0,0,1,opt.front||{});
  face(G,[B,A,D,C],color,0,0,-1,opt);
  face(G,[A,E,I,D],color,-1,0,0,opt);
  face(G,[F,B,C,Gp],color,1,0,0,opt);
  face(G,[I,Gp,C,D],color,0,1,0,opt.top||opt);
  face(G,[A,B,F,E],color,0,-1,0,opt);
}
/* 棱柱（圆柱近似） */
function prism(G,x,y,z,radius,height,color,sides,opt){
  sides=sides||12;opt=opt||{};
  const lo=[],hi=[];
  for(let i=0;i<sides;i++){const a=i/sides*Math.PI*2;lo.push(V(x+Math.cos(a)*radius,y,z+Math.sin(a)*radius));hi.push(V(x+Math.cos(a)*radius,y+height,z+Math.sin(a)*radius))}
  for(let i=0;i<sides;i++){
    const a=(i+.5)/sides*Math.PI*2;
    face(G,[lo[i],lo[(i+1)%sides],hi[(i+1)%sides],hi[i]],color,Math.cos(a),0,Math.sin(a),opt);
  }
  face(G,hi,color,0,1,0,opt.top||opt);
}
/* 纸张：四边形 + 厚度层 + 内容 + 浮动标记 */
const PAPER_PX={fin:[230,300],esg:[280,350]};
function paperQuad(cx,cy,cz,ww,hh,ry,rz){
  const c1=Math.cos(ry),s1=Math.sin(ry),c2=Math.cos(rz),s2=Math.sin(rz);
  const co=(ux,uy)=>{const x1=ux*c1,z1=-ux*s1;return V(cx+x1*c2-uy*s2,cy+x1*s2+uy*c2,cz+z1)};
  return [co(-ww/2,hh/2),co(ww/2,hh/2),co(ww/2,-hh/2),co(-ww/2,-hh/2)];
}
function withQuad(ps,uw,uh,fn){
  const A=ps[0],B=ps[1],D=ps[3];
  ctx.save();
  ctx.transform((B.x-A.x)/uw,(B.y-A.y)/uw,(D.x-A.x)/uh,(D.y-A.y)/uh,A.x,A.y);
  ctx.beginPath();ctx.rect(0,0,uw,uh);ctx.clip();
  fn();ctx.restore();
}
function paperContent(kind,uw,uh,t){
  if(kind==='esg'){
    ctx.fillStyle=MAT.silverD;ctx.font='600 11px Georgia';
    ctx.fillText('DOCUMENT 02 / SUSTAINABILITY',24,36);
    ctx.fillStyle=MAT.graphite;ctx.font='600 68px Georgia';ctx.fillText('ESG',20,124);
    ctx.fillStyle=MAT.silverDD;ctx.font='600 13px sans-serif';ctx.fillText('环境与社会责任报告 / 2025',24,150);
    ctx.fillStyle=MAT.mistD;for(let i=0;i<4;i++)ctx.fillRect(24,178+i*19,224-i*30,3);
    const bars=[34,56,30,70,50,80];
    for(let i=0;i<6;i++){ctx.fillStyle=i===4?MAT.copper:'#CFCCC7';ctx.fillRect(28+i*42,300-bars[i],26,bars[i])}
    ctx.strokeStyle=MAT.silver;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(24,302);ctx.lineTo(276,302);ctx.stroke();
    /* 数据行：数值差异以铜红标记 */
    ctx.font='600 12px Georgia';ctx.fillStyle=MAT.silverDD;
    ctx.fillText('范围一　12,480',24,332);ctx.fillText('范围二　45,120',152,332);
    ctx.strokeStyle=MAT.copper;ctx.lineWidth=1.2;
    ctx.strokeRect(146,320,118,18);
    ctx.fillStyle=MAT.copper;ctx.font='700 11px Georgia';ctx.fillText('Δ 待核验',190,332);
    ctx.fillStyle=MAT.copper;ctx.fillRect(0,uh-54,uw,54);
    ctx.fillStyle=MAT.paper;ctx.font='700 16px sans-serif';ctx.fillText('DISCLOSURE FLAGGED / 口径待核验',22,uh-20);
  }
  if(kind==='fin'){
    ctx.fillStyle=MAT.silverD;ctx.font='600 10px Georgia';ctx.fillText('DOCUMENT 01 / ANNUAL',20,30);
    ctx.fillStyle=MAT.graphite;ctx.font='600 30px Georgia';ctx.fillText('2025 年报',18,68);
    ctx.fillStyle=MAT.mistD;ctx.fillRect(18,82,152,3);
    const pts=[[20,224],[58,200],[88,210],[128,162],[162,172],[204,120]];
    ctx.strokeStyle=MAT.graphite;ctx.lineWidth=2;ctx.lineJoin='round';
    ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();
    for(const p of pts){ctx.fillStyle=MAT.paper;ctx.beginPath();ctx.arc(p[0],p[1],4,0,Math.PI*2);ctx.fill();ctx.strokeStyle=MAT.graphite;ctx.lineWidth=1.4;ctx.stroke()}
    ctx.fillStyle=MAT.mistD;for(let i=0;i<3;i++)ctx.fillRect(20,244+i*15,180-i*40,3);
    ctx.fillStyle=MAT.copper;ctx.fillRect(20,uh-26,54,3);
    ctx.fillStyle=MAT.copper;ctx.font='700 10px Georgia';ctx.fillText('关系示意 · 非核验数据',80,uh-23);
  }
}
function addPaper(G,cx,cy,cz,ww,hh,ry,rz,kind){
  const q=paperQuad(cx,cy,cz,ww,hh,ry,rz);
  /* 厚度：沿纸面背向叠 3 层灰面（更远，先绘制） */
  const nx=Math.sin(ry)*.5,nz=Math.cos(ry)*.5;
  for(let i=3;i>=1;i--){
    const qi=q.map(p=>V(p.x-nx*.045*i,p.y-.03*i,p.z-nz*.045*i));
    face(G,qi,shade(MAT.mistD,.9-i*.05),nx*0.3,-.6,nz*0.3,{noEdge:true});
  }
  const sh=q.map(p=>V(p.x-.05,p.y-.09,p.z-.13));
  face(G,sh,'rgba(37,37,37,.20)',0,-1,0,{noEdge:true});
  const px=PAPER_PX[kind]||[220,280];
  const _px=px[0],_py=px[1];
  face(G,q,MAT.paper,0,0,1,{metal:true,draw:ps=>withQuad(ps,_px,_py,()=>paperContent(kind,_px,_py)),
    flip:(ps,t)=>{
      /* 翻页：右上角周期性掀起 */
      const cyc=(t*.22)%1,kk=cyc<.12?Math.sin(cyc/.12*Math.PI):0;
      if(kk<=.01)return;
      const A=ps[0],B=ps[1],cc=ps[2];
      const fx=mix(A.x,B.x,.62),fy=mix(A.y,B.y,.62);
      const dx=cc.x-B.x,dy=cc.y-B.y;
      const lift=kk*.24;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(B.x,B.y);
      ctx.quadraticCurveTo(fx+dx*lift*.5,fy+dy*lift*.5,fx-dx*lift,fy-dy*lift);
      ctx.lineTo(mix(B.x,cc.x,.55),mix(B.y,cc.y,.55));
      ctx.closePath();
      const g=ctx.createLinearGradient(B.x,B.y,mix(B.x,cc.x,.6),mix(B.y,cc.y,.6));
      g.addColorStop(0,shade(MAT.mistD,.86));g.addColorStop(1,shade(MAT.paper,1.0));
      ctx.fillStyle=g;ctx.fill();
      ctx.strokeStyle='rgba(30,30,30,.3)';ctx.lineWidth=.8;ctx.stroke();
      ctx.restore();
    }});
}
/* 烟雾粒子构建 */
function buildSmoke(G,points,per,spread,rise){
  G.smoke=[];
  for(let i=0;i<points.length;i++){
    for(let j=0;j<per;j++){
      G.smoke.push({src:points[i],j,per,ph:i*1.7+j*.83,seed:(i*37+j*11)%100,spread,rise});
    }
  }
}
function smokeParticlePos(s,t,G){
  const age=(t*.085+s.seed*.01+s.j*.061)%1;
  const ph=s.ph+age*5;
  const swirl=Math.sin(ph)*(s.spread*.35+age*s.spread);
  return V(
    s.src.x+swirl*.7+age*.42,
    s.src.y+age*s.rise,
    s.src.z+Math.cos(ph)*(s.spread*.6+age*s.spread)
  );
}

/* ---------------- 构建：左侧装置（财务数据柱阵） ---------------- */
(function buildA(){
  const G=GROUPS.a;
  /* 展台：双层薄板基座 */
  box(G,0,-1.34,0,10.8,.4,5.4,MAT.silverDD);
  box(G,0,-1.02,0,10.2,.24,4.9,MAT.mistD);
  box(G,0,-.85,0,10.0,.06,4.7,MAT.paper,{});
  /* K 线柱阵：13 根，细柱 + 顶盖，前后错落 */
  const vals=[.9,1.4,1.75,1.5,2.25,2.7,2.35,3.35,3.75,3.5,4.45,5.0,5.85];
  for(let j=0;j<13;j++){
    const x=-4.55+j*.76,hh2=vals[j],z=(j%3)*.36-.36;
    const isFlag=(j===12);          /* 唯一差异柱：铜红 */
    const base=isFlag?MAT.copper:(j===6?MAT.mist:(j===9?MAT.mistD:MAT.paper));
    box(G,x,-.82+hh2/2,z,.44,hh2,.44,base,{metal:true});
    box(G,x,-.82+hh2+.05,z,.5,.1,.5,MAT.graphite,{});
  }
  G.linePts=vals.map((v,j)=>V(-4.55+j*.76,-.82+v+.26,(j%3)*.36-.36));
  G.endPt=V(-4.55+12*.76+.02,-.82+vals[12]+.5,(12%3)*.36-.36);
  /* 悬浮年报 */
  addPaper(G,-1.85,5.15,1.5,2.3,2.95,.42,-.05,'fin');
  /* 细坐标轴：沿基座前缘的一条细线 + 刻度 */
  G.axis=[];
  for(let j=0;j<13;j++)G.axis.push(V(-4.55+j*.76,-.78,2.28));
  /* 底座角标 */
  box(G,-5.4,-.62,2.5,.09,.36,.09,MAT.silverD,{});
  box(G,5.4,-.62,2.5,.09,.36,.09,MAT.silverD,{});
  /* 数据节点标记（铜红差异标记放在最高柱顶部） */
  G.ringPt=V(-4.55+12*.76,-.82+vals[12]+.72,(12%3)*.36-.36);
})();

/* ---------------- 构建：右侧装置（工业排放设施） ---------------- */
(function buildB(){
  const G=GROUPS.b;
  box(G,0,-1.34,0,10.8,.4,5.4,MAT.silverDD);
  box(G,0,-1.02,0,10.2,.24,4.9,MAT.mistD);
  box(G,0,-.85,0,10.0,.06,4.7,MAT.paper,{});
  /* 主厂房：双层体量 + 女儿墙 + 窗带 + 屋顶机组 */
  box(G,.7,-.32,.5,4.3,1.8,2.6,MAT.paper,{metal:true});
  box(G,.7,.58,.5,4.55,.9,2.75,MAT.mist,{metal:true});
  box(G,.7,1.12,.5,4.72,.16,2.9,MAT.silverD,{});
  for(let k=0;k<5;k++)box(G,-1.05+k*.88,.28,1.82,.42,.62,.07,MAT.graphite,{});
  box(G,.7,1.32,.5,.9,.26,.9,MAT.silverD,{});
  box(G,-1.3,1.3,.5,.5,.22,.5,MAT.mistD,{});
  box(G,2.5,1.28,.5,.6,.16,.6,MAT.mist,{});
  /* 高塔群 */
  const towers=[{x:-2.9,z:-1.5,h:4.3,wd:.9},{x:3.8,z:-1.05,h:5.1,wd:1.0},{x:-.9,z:-2.0,h:3.1,wd:.75}];
  for(const t of towers){
    box(G,t.x,-.82+t.h/2,t.z,t.wd,t.h,t.wd,MAT.paper,{metal:true});
    box(G,t.x,-.82+t.h*.42,t.z,t.wd+.08,.34,t.wd+.08,MAT.silverD,{});
    box(G,t.x,-.82+t.h+.075,t.z,t.wd+.14,.15,t.wd+.14,MAT.graphite,{});
  }
  /* 烟囱：三根不同高度，椭圆截面 */
  const stacks=[[-4.5,.85,3.3,.4],[1.9,1.35,4.0,.46],[4.6,-.35,2.7,.33]];
  for(const s2 of stacks){
    prism(G,s2[0],-.82,s2[1],s2[3],s2[2],MAT.mist,12,{metal:true});
    prism(G,s2[0],-.82+s2[2]-.3,s2[1],s2[3]+.04,.26,MAT.silverD,12,{});
    prism(G,s2[0],-.82+s2[2]+.06,s2[1],s2[3]*.74,.12,MAT.graphite,12,{});
  }
  buildSmoke(G,[V(-4.5,2.6,.85),V(1.9,3.3,1.35),V(4.6,2.0,-.35)],12,.55,3.7);
  /* 悬浮 ESG 报告（主视觉） */
  addPaper(G,.35,4.5,2.0,2.7,3.35,-.28,.04,'esg');
  /* 前缘管线细节 */
  for(let k=0;k<5;k++)box(G,-4.4+k*.7,-.7,2.42,.5,.1,.1,MAT.silverD,{});
  prism(G,5.3,-.82,-1.6,.34,.5,MAT.mistD,8,{});
  G.ringPt=V(.35,4.5,2.0);
})();

/* ---------------- 投影 ---------------- */
function tp(G,p){
  const cy=Math.cos(G.yaw),sy=Math.sin(G.yaw);
  const x1=p.x*cy+p.z*sy;
  const z1=-p.x*sy+p.z*cy;
  const cp=Math.cos(G.pitch),sp=Math.sin(G.pitch);
  const y1=p.y*cp-z1*sp;
  const z2=p.y*sp+z1*cp;
  const depth=G.dist-z2;
  if(depth<2)return null;
  const s=G.focal/depth;
  return {x:G.sx+x1*s,y:G.sy-y1*s,z:depth,sc:s};
}
function paintPoly(pts,fill,stroke,alpha){
  const prev=ctx.globalAlpha;
  ctx.globalAlpha=prev*(alpha==null?1:alpha);
  ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);
  for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i].x,pts[i].y);
  ctx.closePath();
  if(fill){ctx.fillStyle=fill;ctx.fill()}
  if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=.75;ctx.stroke()}
  ctx.globalAlpha=prev;
}
function toPath(pts){ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i].x,pts[i].y);ctx.closePath()}
// 只约束标题、左右页边与首页底部；两个模型共用完整舞台。
function fitScene(G){
  if(!G.envelope)G.envelope=[...new Map(G.faces.flatMap(face=>face.p).map(p=>[`${p.x},${p.y},${p.z}`,p])).values()];
  const heading=home.querySelectorById('heroHeading');
  const maskTop=(heading.offsetTop+heading.offsetHeight)+'px';
  if(stage.style.getPropertyValue('--scene-top')!==maskTop)stage.style.setProperty('--scene-top',maskTop);
  const top=heading.offsetTop+heading.offsetHeight+18,bottom=h-(w<760?42:82),side=12;
  const bounds=()=>{const points=G.envelope.map(p=>tp(G,p)).filter(Boolean);return {left:Math.min(...points.map(p=>p.x)),right:Math.max(...points.map(p=>p.x)),top:Math.min(...points.map(p=>p.y)),bottom:Math.max(...points.map(p=>p.y))};};
  let rect=bounds();
  G.focal*=Math.max(.05,Math.min(1,(w-side*2)/(rect.right-rect.left),(bottom-top)/(rect.bottom-rect.top)));rect=bounds();
  const shift=Math.max(0,side-rect.left)-Math.max(0,rect.right-(w-side));
  // 边界校正只作用于本帧，不能写回用户拖动位置并逐帧积累。
  G.sx+=shift;
  G.sy+=Math.max(0,top-rect.top)-Math.max(0,rect.bottom-bottom);
  return bounds();
}
function drawGroup(G,t){
  const mob=w<760;
  const rv=easeOut(G.reveal);
  const lift=(1-rv)*90;
  if(mob){G.sx=w*.5+(G.panX||0);G.sy=h*(G.id==='a'?.48:.82)+lift;G.focal=Math.min(w*.9,h*.24)}
  else{G.sx=w*(G.id==='a'?.235:.765)+(G.panX||0);G.sy=h*.76+lift;G.focal=Math.min(w*.58,h*.72)}
  const fitted=fitScene(G);
  // 先按默认尺寸适配舞台，再围绕模型中心缩放，避免缩放被适配抵消或带动位置。
  const cx=(fitted.left+fitted.right)/2,cy=(fitted.top+fitted.bottom)/2;
  G.sx=cx+(G.sx-cx)*G.zoom;G.sy=cy+(G.sy-cy)*G.zoom;G.focal*=G.zoom;
  const baseAlpha=rv*G.alpha;
  if(baseAlpha<=.01)return;
  /* 基座柔和落地阴影（屏幕空间） */
  const gc=tp(G,V(0,-1.5,0));
  if(gc){
    ctx.save();ctx.globalAlpha=baseAlpha*.5;
    const rr=G.focal*.34;
    const g2=ctx.createRadialGradient(gc.x,gc.y+rr*.12,rr*.1,gc.x,gc.y+rr*.12,rr);
    g2.addColorStop(0,'rgba(60,58,55,.30)');g2.addColorStop(1,'rgba(60,58,55,0)');
    ctx.fillStyle=g2;
    ctx.beginPath();ctx.ellipse(gc.x,gc.y+rr*.12,rr,rr*.32,0,0,Math.PI*2);ctx.fill();
    ctx.restore();
  }
  /* 队列：面片 + 烟雾粒子统一深度排序 */
  const queue=[];
  for(const f of G.faces){
    const fy=f.float?Math.sin(t*.8+f.ph)*.07:0;
    const ps=[];let ok=true;
    for(const p of f.p){const q=tp(G,fy?V(p.x,p.y+fy,p.z):p);if(!q){ok=false;break}ps.push(q)}
    if(!ok)continue;
    let d=0;for(const q of ps)d+=q.z;
    queue.push({f,ps,depth:d/ps.length});
  }
  if(G.smoke){
    for(const s of G.smoke){
      const pos=smokeParticlePos(s,t,G);
      const q=tp(G,pos);
      if(!q)continue;
      queue.push({smoke:true,s,q,depth:q.z});
    }
  }
  queue.sort((p,q)=>q.depth-p.depth);
  ctx.save();ctx.globalAlpha=baseAlpha;
  ctx.beginPath();ctx.rect(0,0,w,h);ctx.clip();
  for(const it of queue){
    if(it.smoke){
      /* 体积烟雾：仅将原有灰色改为红棕色，形态与透明度保持原有设置 */
      const s=it.s,q=it.q;
      const age=(t*.085+s.seed*.01+s.j*.061)%1;
      const r=(.38+age*1.1)*q.sc;
      if(r<2)continue;
      const op=(1-age)*(.62+ (s.j%3)*.07);
      let g2=ctx.createRadialGradient(q.x-r*.22,q.y-r*.2,r*.05,q.x,q.y,r);
      g2.addColorStop(0,'rgba(237,116,52,'+Math.min(op*1.05,.85)+')');
      g2.addColorStop(.42,'rgba(190,57,31,'+(op*.62)+')');
      g2.addColorStop(.75,'rgba(102,35,27,'+(op*.30)+')');
      g2.addColorStop(1,'rgba(102,35,27,0)');
      ctx.fillStyle=g2;ctx.beginPath();ctx.arc(q.x,q.y,r,0,Math.PI*2);ctx.fill();
      continue;
    }
    const f=it.f;
    const k=litK(G,f);
    let fill;
    if(f.metal){
      /* 金属面：竖直渐变（上亮下暗）；小面直接用纯色以保证性能 */
      let miny=1e9,maxy=-1e9,minx=1e9,maxx=-1e9;
      for(const p of it.ps){if(p.y<miny)miny=p.y;if(p.y>maxy)maxy=p.y;if(p.x<minx)minx=p.x;if(p.x>maxx)maxx=p.x}
      if(maxy-miny>14&&maxx-minx>10){
        const gr=ctx.createLinearGradient(0,miny,0,maxy);
        gr.addColorStop(0,shade(f.c,Math.min(k*1.1,1.16)));
        gr.addColorStop(.55,shade(f.c,k));
        gr.addColorStop(1,shade(f.c,k*.72));
        fill=gr;
      }else fill=shade(f.c,k*1.04);
    }else{
      fill=shade(f.c,k);
    }
    paintPoly(it.ps,fill,f.noEdge?null:edgeOf(k),f.alpha);
    if(f.draw)f.draw(it.ps);
    if(f.flip)f.flip(it.ps,t);
  }
  ctx.restore();
  /* 组内前景 overlay */
  if(G.id==='a')overlayA(G,t,baseAlpha);
  else overlayB(G,t,baseAlpha);
}

/* ---------- 左组 overlay：细线数据轨迹 + 坐标轴 ---------- */
function overlayA(G,t,alpha){
  ctx.save();ctx.globalAlpha=alpha;
  /* 基座前缘细坐标轴 */
  const A0=tp(G,G.axis[0]),A1=tp(G,G.axis[12]);
  if(A0&&A1){
    ctx.strokeStyle='rgba(37,37,37,.35)';ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(A0.x,A0.y);ctx.lineTo(A1.x,A1.y);ctx.stroke();
    G.axis.forEach((p,i)=>{const q=tp(G,p);if(!q)return;ctx.beginPath();ctx.moveTo(q.x,q.y);ctx.lineTo(q.x,q.y-(i%2?4:6));ctx.strokeStyle='rgba(37,37,37,.3)';ctx.lineWidth=1;ctx.stroke()});
  }
  /* 数据轨迹：细深灰线 + 节点圆点 + 铜红终点 */
  const ps=G.linePts.map(p=>tp(G,p)).filter(Boolean);
  if(ps.length>1){
    ctx.beginPath();ps.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
    ctx.strokeStyle='rgba(30,30,30,.62)';ctx.lineWidth=1.5;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();
    for(const p of ps){ctx.beginPath();ctx.arc(p.x,p.y,2.6,0,Math.PI*2);ctx.fillStyle=MAT.paper;ctx.fill();ctx.strokeStyle='rgba(30,30,30,.55)';ctx.lineWidth=1.2;ctx.stroke()}
    /* 流动数据点 */
    const fr=((t*.2)%1)*(ps.length-1),j=Math.floor(fr),kk=fr-j;
    if(j<ps.length-1){
      const x=mix(ps[j].x,ps[j+1].x,kk),y=mix(ps[j].y,ps[j+1].y,kk);
      ctx.beginPath();ctx.arc(x,y,3.4,0,Math.PI*2);ctx.fillStyle=MAT.copper;ctx.fill();
    }
  }
  /* 终点差异标记：铜红菱形 + 细引线 */
  const ep=tp(G,G.endPt);
  if(ep){
    ctx.save();ctx.translate(ep.x,ep.y);ctx.rotate(Math.PI/4);
    ctx.fillStyle=MAT.copper;ctx.fillRect(-4.5,-4.5,9,9);
    ctx.restore();
    ctx.strokeStyle='rgba(164,85,73,.55)';ctx.lineWidth=1;ctx.setLineDash([3,4]);
    ctx.beginPath();ctx.moveTo(ep.x+8,ep.y-6);ctx.lineTo(ep.x+58,ep.y-30);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle=MAT.copperD;ctx.font='600 10px Georgia';ctx.fillText('Δ FLAG',ep.x+62,ep.y-27);
  }
  ctx.restore();
}
/* ---------- 右组 overlay：烟囱信号灯 ---------- */
function overlayB(G,t,alpha){
  ctx.save();ctx.globalAlpha=alpha;
  const pts=[[-4.5,3.1,.85],[1.9,3.8,1.35],[4.6,2.5,-.35]];
  pts.forEach((pp,i)=>{
    const q=tp(G,V(pp[0],pp[1],pp[2]));if(!q)return;
    const blink=(Math.sin(t*1.6+i*2.1)+1)/2;
    ctx.beginPath();ctx.arc(q.x,q.y,2.4,0,Math.PI*2);
    ctx.fillStyle='rgba(164,85,73,'+(.35+blink*.6)+')';ctx.fill();
  });
  ctx.restore();
}

/* ---------------- 环境层（克制） ---------------- */
const ENV=[];
(function buildEnv(){
  let seed=53;const rnd=()=>{seed=(seed*9301+49297)%233280;return seed/233280};
  let guard=0;
  while(ENV.length<28&&guard++<300){
    const x=rnd(),y=rnd();
    if(x>.3&&x<.7&&y<.48)continue;
    ENV.push({x,y,kind:Math.floor(rnd()*4),size:2.2+rnd()*5,ph:rnd()*6.28,sp:.2+rnd()*.4,depth:.4+rnd()*.8,al:.14+rnd()*.24});
  }
})();
function drawEnv(t){
  for(const e of ENV){
    const px=e.x*w;
    const py=e.y*h+Math.sin(t*e.sp+e.ph)*8;
    ctx.save();ctx.globalAlpha=e.al;
    ctx.strokeStyle='rgba(37,37,37,1)';ctx.fillStyle='rgba(37,37,37,1)';ctx.translate(px,py);
    if(e.kind===0){ctx.beginPath();ctx.arc(0,0,e.size*.5,0,Math.PI*2);ctx.fill()}
    else if(e.kind===1){ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(-e.size,0);ctx.lineTo(e.size,0);ctx.moveTo(0,-e.size);ctx.lineTo(0,e.size);ctx.stroke()}
    else if(e.kind===2){ctx.lineWidth=1;ctx.beginPath();ctx.arc(0,0,e.size*1.4,0,Math.PI*2);ctx.stroke()}
    else{ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(-e.size*1.3,-e.size*.6);ctx.lineTo(e.size*1.3,e.size*.6);ctx.stroke()}
    ctx.restore();
  }
}
/* 小型报告页与数据条仅作背景图形，不承载企业事实。 */
function drawFragments(t){
  const fragments=[[.075,.32,-.13,0],[.91,.28,.15,1],[.39,.43,.12,0],[.65,.39,-.16,1],[.06,.76,.2,2],[.94,.72,-.25,2]];
  for(const [x,y,angle,kind] of fragments){
    const scale=w<760?.55:Math.min(1,w/1400);
    ctx.save();ctx.translate(x*w,y*h+Math.sin(t*.35+x*12)*6);ctx.rotate(angle);ctx.scale(scale,scale);ctx.globalAlpha=.56;
    if(kind===2){ctx.fillStyle=MAT.copper;ctx.fillRect(-30,-3,60,6);ctx.fillStyle=MAT.silverD;ctx.fillRect(-16,12,46,2);}
    else{
      ctx.fillStyle=MAT.paper;ctx.shadowColor='rgba(37,37,37,.12)';ctx.shadowBlur=14;ctx.fillRect(-24,-35,48,70);ctx.shadowBlur=0;
      ctx.strokeStyle=MAT.silverD;ctx.lineWidth=.8;ctx.strokeRect(-24,-35,48,70);ctx.fillStyle=MAT.copper;ctx.fillRect(-17,-25,20,2);
      ctx.fillStyle=MAT.silverD;
      for(let i=0;i<4;i++)ctx.fillRect(-17,-13+i*7,28-(i%2)*7,1);
      if(kind===1){for(let i=0;i<4;i++){ctx.fillStyle=i===3?MAT.copper:MAT.silver;ctx.fillRect(-17+i*9,25-i*4,5,6+i*4);}}
      else{ctx.strokeStyle=MAT.copper;ctx.beginPath();ctx.moveTo(-17,25);ctx.lineTo(-7,18);ctx.lineTo(2,21);ctx.lineTo(16,10);ctx.stroke();}
    }
    ctx.restore();
  }
}
/* 两侧关联连线：细虚线 + 流动点 */
function dashTrail(t){
  const A=tp(GROUPS.a,GROUPS.a.endPt),B=tp(GROUPS.b,V(.35,4.5,2.0));
  if(!A||!B)return;
  const rvA=easeOut(GROUPS.a.reveal),rvB=easeOut(GROUPS.b.reveal);
  const vis=Math.min(rvA,rvB);
  if(vis<.2)return;
  const cx=(A.x+B.x)/2,cy=Math.min(A.y,B.y)-h*.07;
  ctx.save();ctx.globalAlpha=vis;
  ctx.beginPath();ctx.moveTo(A.x,A.y);ctx.quadraticCurveTo(cx,cy,B.x,B.y);
  ctx.setLineDash([7,7]);ctx.lineDashOffset=-((t*30)%14);
  ctx.strokeStyle='rgba(164,85,73,.55)';ctx.lineWidth=1.1;ctx.stroke();
  ctx.setLineDash([]);
  for(let i=0;i<2;i++){
    const k=(t*.24+i*.5)%1;
    const x=(1-k)*(1-k)*A.x+2*(1-k)*k*cx+k*k*B.x;
    const y=(1-k)*(1-k)*A.y+2*(1-k)*k*cy+k*k*B.y;
    ctx.fillStyle=MAT.copper;ctx.beginPath();ctx.arc(x,y,2.6,0,Math.PI*2);ctx.fill();
  }
  ctx.restore();
}

/* ---------------- 渲染 ---------------- */
function render(t){
  ctx=contexts.background;
  ctx.clearRect(0,0,w,h);
  drawEnv(t);
  drawFragments(t);
  for(const G of Object.values(GROUPS)){
    const signature=[rasterRevision,G.zoom,G.yaw,G.pitch,G.reveal,G.panX].join('|');
    if(prefersReduced&&G.lastFrame===signature)continue;
    G.lastFrame=signature;
    ctx=contexts[G.id];ctx.clearRect(0,0,w,h);
    ctx.save();drawGroup(G,t);ctx.restore();
  }
  ctx=contexts.background;dashTrail(t);
  moveLabels();
}

/* ---------------- 标签跟随 ---------------- */
const anchors={left:[GROUPS.a,V(-5.6,4.6,.9)],right:[GROUPS.b,V(2.0,6.0,.2)],report:[GROUPS.b,V(.35,4.5,2.0)]};
function moveLabels(){
  for(const key of Object.keys(anchors)){
    const G=anchors[key][0];
    const rv=easeOut(G.reveal);
    const el=home.querySelectorById('tag'+key[0].toUpperCase()+key.slice(1));
    if(!el)continue;
    const p=tp(G,anchors[key][1]);
    const vis=p&&rv>.6;
    el.style.opacity=vis?'1':'0';
    el.style.pointerEvents=vis?'auto':'none';
    if(p){const half=el.offsetWidth/2+12;const minX=half;const maxX=w-half;el.style.left=clamp(p.x,minX,maxX)+'px';const minY=w<760?h*(G.id==='a'?.31:.67):h*.37;const maxY=w<760?h*(G.id==='a'?.53:.88):h*.78;el.style.top=clamp(p.y,minY,maxY)+'px';if(key==='report'){const upper=home.querySelectorById('tagRight');const separation=(upper.offsetHeight+el.offsetHeight)/2+20;el.style.top=Math.max(parseFloat(el.style.top),parseFloat(upper.style.top)+separation)+'px'}}
  }
}

/* ---------------- 主循环 ---------------- */
let t0=null;
let prev=null;
let lastStep=0;
let forceDone=false;
let doneOnce=false;          /* 是否已渲染过一帧完整画面 */
setTimeout(()=>{forceDone=true},1700);   /* 兜底：无论帧调度如何，1.7s 后进入终态 */
function stepFrame(now){
  if(!animationOn)return;
  if(document.hidden&&doneOnce)return;   /* 已渲染完整画面后，视口不可见时才停 */
  if(now-lastStep<6)return;           /* 防同帧重复驱动 */
  lastStep=now;
  if(t0===null){t0=now;prev=now}
  const dt=Math.min((now-prev)/1000,.048);prev=now;
  const tt=now/1000;
  /* 入场时间线：基于真实时间，与帧率无关（确定性） */
  const el=now-t0;
  if(forceDone||prefersReduced){GROUPS.a.revealT=1;GROUPS.b.revealT=1}
  else{
    GROUPS.a.revealT=clamp((el-380)/700,0,1);
    GROUPS.b.revealT=clamp((el-700)/700,0,1);
  }
  const kSlow=1-Math.exp(-dt*7),kFast=1-Math.exp(-dt*9);
  for(const G of Object.values(GROUPS)){
    if(state.dragging!==G.id){
      if(Math.abs(G.velX)>.25){G.dragX=clamp(G.dragX+G.velX*dt*60,-MAXD,MAXD);G.velX*=Math.pow(.9,dt*60)}else G.velX=0;
      if(Math.abs(G.velY)>.25){G.dragY=clamp(G.dragY+G.velY*dt*60,-MAXP,MAXP);G.velY*=Math.pow(.9,dt*60)}else G.velY=0;
    }
    G.reveal=G.revealT;
    G.zoom=mix(G.zoom,G.zoomT,kSlow);if(Math.abs(G.zoom-G.zoomT)<.0001)G.zoom=G.zoomT;
    const breathe=prefersReduced?0:Math.sin(tt*.4+G.breath)*.016;
    const yawTarget=G.baseYaw+G.dragX*.0026+breathe,pitchTarget=clamp(G.basePitch+G.dragY*.0016+breathe*.5,.16,.8);
    G.yaw=mix(G.yaw,yawTarget,kFast);G.pitch=mix(G.pitch,pitchTarget,kFast);
    if(Math.abs(G.yaw-yawTarget)<.0001)G.yaw=yawTarget;
    if(Math.abs(G.pitch-pitchTarget)<.0001)G.pitch=pitchTarget;
  }
  render(prefersReduced?0:tt);
  if(forceDone)doneOnce=true;
}
function frame(now){requestAnimationFrame(frame);stepFrame(now)}
requestAnimationFrame(frame);
/* 兜底补帧：完整画面渲染出来之前，用定时器持续驱动（应对 rAF 节流/后台环境） */
setInterval(()=>{if(!doneOnce)stepFrame(performance.now())},64);

/* ---------------- 分侧交互：滚动通道不注册 wheel 拦截 ---------------- */
const zones={a:home.querySelectorById('model-left'),b:home.querySelectorById('model-right')};
function choose(name){
  const id=name==='left'?'a':name==='right'||name==='report'?'b':name;
  if(!GROUPS[id])return;
  state.active=id;
  layers.a.style.zIndex=id==='a'?'2':'1';layers.b.style.zIndex=id==='b'?'2':'1';
  for(const [key,zone] of Object.entries(zones))zone.classList.toggle('selected',key===id);
}
function notify(s){if(home.hidden||home.getBoundingClientRect().bottom<=0)return;const el=home.querySelectorById('notice');el.textContent=s;el.classList.add('visible');clearTimeout(notify.timer);notify.timer=setTimeout(()=>el.classList.remove('visible'),2400)}
function zoom(G,delta){G.zoomT=clamp(G.zoomT+delta,.6,2.25);home.querySelectorById(G.id==='a'?'model-left-scale':'model-right-scale').value=Math.round(G.zoomT*100)+'%';}
function reset(G){G.panX=0;G.dragX=0;G.dragY=0;G.velX=0;G.velY=0;zoom(G,1-G.zoomT);}
function wheelFor(G,event){if(event.ctrlKey)return;event.preventDefault();choose(G.id);const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?h:1);zoom(G,-delta*.0012);}
home.querySelectorAll('[data-focus]').forEach(button=>{button.addEventListener('click',()=>{choose(button.dataset.focus);zones[state.active].focus({preventScroll:true});});button.addEventListener('wheel',event=>wheelFor(GROUPS[button.dataset.focus==='left'?'a':'b'],event),{passive:false});});
home.querySelectorAll('[data-model-action]').forEach(button=>button.addEventListener('click',()=>{const G=GROUPS[button.dataset.model];choose(G.id);if(button.dataset.modelAction==='reset')reset(G);else zoom(G,button.dataset.modelAction==='zoom-in'?.14:-.14);}));
// 以实际可见模型命中，移到另一侧后仍能重新抓取原模型。
function hitGroup(event){
  const rect=stage.getBoundingClientRect(),x=Math.floor((event.clientX-rect.left)*dpr),y=Math.floor((event.clientY-rect.top)*dpr);
  const heading=home.querySelectorById('heroHeading');
  if(y<0||x<0||x>=canvas.width||y>=canvas.height||event.clientY-rect.top<heading.offsetTop+heading.offsetHeight+16)return null;
  for(const id of [state.active,state.active==='a'?'b':'a'])if(contexts[id].getImageData(x,y,1,1).data[3]>90)return id;
  return null;
}
const surface=home.querySelectorById('top');let moving=null,lastX=0,lastY=0;
surface.addEventListener('pointerdown',event=>{
  if(event.button!==0||event.target.closest('button,a,input,select,textarea'))return;
  const id=hitGroup(event)||event.target.closest('.model-zone')?.dataset.model;
  if(!id)return;
  event.preventDefault();choose(id);moving=GROUPS[id];state.dragging=id;lastX=event.clientX;lastY=event.clientY;moving.velX=0;moving.velY=0;
  zones[id].focus({preventScroll:true});zones[id].classList.add('grabbing');surface.setPointerCapture(event.pointerId);
});
surface.addEventListener('pointermove',event=>{
  const G=moving;if(!G)return;
  const dx=event.clientX-lastX,dy=event.clientY-lastY;
  if(G.zoomT>1.05&&!event.shiftKey){G.panX=(G.panX||0)+dx;G.velX=0;}else{G.dragX=clamp(G.dragX+dx,-MAXD,MAXD);G.velX=dx*.94;}
  G.dragY=clamp(G.dragY+dy,-MAXP,MAXP);G.velY=dy*.9;lastX=event.clientX;lastY=event.clientY;
});
function stopMoving(){if(!moving)return;zones[moving.id].classList.remove('grabbing');if(prefersReduced){moving.velX=0;moving.velY=0;}moving=null;state.dragging=null;}
for(const event of ['pointerup','pointercancel','lostpointercapture'])surface.addEventListener(event,stopMoving);
surface.addEventListener('wheel',event=>{if(event.defaultPrevented)return;const id=hitGroup(event);if(id)wheelFor(GROUPS[id],event);},{passive:false});
for(const [id,zone] of Object.entries(zones)){
  const G=GROUPS[id];
  zone.addEventListener('dblclick',event=>reset(GROUPS[hitGroup(event)||id]));
  zone.addEventListener('wheel',event=>wheelFor(GROUPS[hitGroup(event)||id],event),{passive:false});
  zone.addEventListener('keydown',event=>{
    if(event.ctrlKey||event.metaKey||event.altKey)return;
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','Home'].includes(event.key))return;
    event.preventDefault();choose(id);G.velX=0;G.velY=0;
    if(event.key==='ArrowLeft'){if(G.zoomT>1.05&&!event.shiftKey)G.panX=(G.panX||0)-26;else G.dragX=clamp(G.dragX-26,-MAXD,MAXD);}
    if(event.key==='ArrowRight'){if(G.zoomT>1.05&&!event.shiftKey)G.panX=(G.panX||0)+26;else G.dragX=clamp(G.dragX+26,-MAXD,MAXD);}
    if(event.key==='ArrowUp')G.dragY=clamp(G.dragY-20,-MAXP,MAXP);
    if(event.key==='ArrowDown')G.dragY=clamp(G.dragY+20,-MAXP,MAXP);
    if(event.key==='+'||event.key==='=')zoom(G,.1);
    if(event.key==='-')zoom(G,-.1);
    if(event.key==='Home')reset(G);
  });
}
window.addEventListener('pointermove',event=>{cursorEl.style.left=event.clientX+'px';cursorEl.style.top=event.clientY+'px'});

/* ---------------- 入场时间线（标题 / 控件） ---------------- */
const heroEl=home.querySelectorById('top');
[['s1',120],['s2',340],['s3',620],['s4',980]].forEach(([cls,ms])=>setTimeout(()=>heroEl.classList.add(cls),prefersReduced?0:ms));

/* ---------------- 六阶段流程（n8n 式节点图） ---------------- */
const flows=[
  ['以同一企业、同一期间建立核对任务','接入年度报告和可持续发展报告，登记来源、版本与分析任务。'],
  ['先对齐，再比较','确认企业主体、年度、披露边界和关键指标口径，必要时保留人工确认。'],
  ['让每个差异都有原文出处','定位相关段落、页码与数据表，保留可追溯的证据片段。'],
  ['可计算的部分交给规则','运用结构化规则检查口径与数值关系，避免把确定性运算交由模型猜测。'],
  ['把冲突解释成待核验问题','结合上下文与知识依据解释差异，区分计算错误、范围变化与正常披露差别。'],
  ['复核结果，留存核验过程','展示来源、规则与人工校验记录，形成可追溯的分析输出；不替代专业判断。']
];
const flowGlow=home.querySelectorById('flowGlow');
const segPaths=['M50 100 C 134 58, 134 58, 218 100','M218 100 C 302 142, 302 142, 386 100','M386 100 C 470 58, 470 58, 554 100','M554 100 C 638 142, 638 142, 722 100','M722 100 C 806 58, 806 58, 890 100'];
home.querySelectorAll('.node').forEach(b=>b.addEventListener('click',()=>{
  const i=Number(b.dataset.step);
  home.querySelectorAll('.node').forEach(s=>s.classList.toggle('active',s===b));
  home.querySelectorById('flowTitle').textContent=flows[i][0];
  home.querySelectorById('flowBody').textContent=flows[i][1];
  home.querySelectorById('flowNumber').textContent=String(i+1).padStart(2,'0');
  /* 点亮到此节点为止的连线 */
  if(i===0){flowGlow.style.opacity=0}
  else{flowGlow.setAttribute('d',segPaths.slice(0,i).join(' '));flowGlow.style.opacity=1}
}));

/* ---------------- 滚动揭示 ---------------- */
const io2=new IntersectionObserver(es=>{
  es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('on');io2.unobserve(e.target)}});
},{threshold:.14,rootMargin:'0px 0px -6% 0px'});
home.querySelectorAll('.rv').forEach(el=>io2.observe(el));
const io=new IntersectionObserver(entries=>{for(const e of entries)if(e.target===stage)animationOn=e.isIntersecting||e.intersectionRatio>0;},{threshold:0,rootMargin:'240px'});
io.observe(stage);
setTimeout(()=>notify('放大后左右拖动可移动 · Shift 拖动旋转 · 中间可滚动'),2600);
})();

// 首页与工作台同页滚动：入口只负责定位，不再切换整屏。
document.querySelectorAll('[data-enter-connectivity]').forEach(link=>link.addEventListener('click',event=>{const workspace=document.getElementById('connectivity-root');if(!workspace)return;event.preventDefault();document.getElementById('notice')?.classList.remove('visible');history.replaceState(null,'','#connectivity-root');window.scrollTo({top:workspace.getBoundingClientRect().top+window.scrollY,behavior:'smooth'});setTimeout(()=>document.getElementById('cn-workspace')?.focus({preventScroll:true}),420);}));
