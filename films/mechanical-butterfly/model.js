// Concept dimensions in model units, not measured engineering or flight data.
export const P = Object.freeze({crank: .23, rod: .77, rocker: .43, hingeX: .66,
  hingeY: .08, hz: 2.4, playback: .25, duration: 26, span: 14.5});
export const clamp = (v,a=0,b=1)=>Math.max(a,Math.min(b,v));
export const smooth = (a,b,t)=>{const u=clamp((t-a)/(b-a));return u*u*(3-2*u);};
export const pulse = (t,a,b,c,d)=>smooth(a,b,t)*(1-smooth(c,d,t));
export function linkage(phase) {
  const p=[P.crank*Math.cos(phase),P.crank*Math.sin(phase)];
  const h=[P.hingeX,P.hingeY], dx=p[0]-h[0],dy=p[1]-h[1],d=Math.hypot(dx,dy);
  const a=(P.rocker**2-P.rod**2+d*d)/(2*d),height=Math.sqrt(Math.max(0,P.rocker**2-a*a));
  const q=[h[0]+a*dx/d+height*dy/d,h[1]+a*dy/d-height*dx/d];
  return {p,q,angle:Math.atan2(q[1]-h[1],q[0]-h[0])-Math.PI/2,
    closure:Math.abs(Math.hypot(q[0]-p[0],q[1]-p[1])-P.rod)};
}
export function stateAt(t, options={}) {
  const hz=options.hz??P.hz, phase=t*hz*P.playback*2*Math.PI;
  const front=linkage(phase),back=linkage(phase-.32);
  const explode=options.explode??pulse(t,16,17.6,20,22);
  const shell=options.shell??Math.max(pulse(t,8,9.5,14.8,16),explode);
  const fly=smooth(23.5,26,t), hover=.07*Math.sin(phase*2);
  return {t,hz,phase,front,back,explode,shell,fly,hover,
    rpm:hz*60, angle:front.angle*180/Math.PI,backAngle:back.angle*180/Math.PI,
    stroke:Math.hypot(front.q[0]-front.p[0],front.q[1]-front.p[1]),
    beat:t<4?0:t<8?1:t<12?2:t<16?3:t<21?4:t<24?5:6};
}
