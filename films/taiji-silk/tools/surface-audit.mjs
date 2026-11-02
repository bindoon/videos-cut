// Inspect the actual rendered skin topology after welding duplicate UV vertices.
// Only the covered thigh may be cut; the ankle must remain a closed native surface.
export function auditLowerLimb(mesh){
 const position=mesh.geometry.attributes.position,index=mesh.geometry.index;
 const byPosition=new Map(),canonical=[],weld=new Map();
 function vertex(i){if(weld.has(i))return weld.get(i);const p=[position.getX(i),position.getY(i),position.getZ(i)],key=p.map(x=>x.toFixed(5)).join(',');let id=byPosition.get(key);if(id===undefined){id=canonical.length;byPosition.set(key,id);canonical.push(p)}weld.set(i,id);return id}
 const faces=[];for(let i=0;i<index.count;i+=3)faces.push([vertex(index.getX(i)),vertex(index.getX(i+1)),vertex(index.getX(i+2))]);
 function edgesFor(triangles){const edges=new Map();for(const face of triangles)for(let j=0;j<3;j++){const a=face[j],b=face[(j+1)%3];if(a===b)continue;const key=a<b?`${a},${b}`:`${b},${a}`;edges.set(key,(edges.get(key)||0)+1)}return edges}
 const edges=edgesFor(faces),adjacency=new Map();let openAnkleEdges=0;
 function isAnkle(a,b){const p=canonical[a],q=canonical[b],y=(p[1]+q[1])/2,x=(p[0]+q[0])/2;return y>.04&&y<.30&&Math.abs(x)>.08}
 for(const [key,count] of edges){const [a,b]=key.split(',').map(Number);if(count===1&&isAnkle(a,b))openAnkleEdges++;if(!adjacency.has(a))adjacency.set(a,[]);if(!adjacency.has(b))adjacency.set(b,[]);adjacency.get(a).push(b);adjacency.get(b).push(a)}
 const connected=[];for(const sign of [-1,1]){const start=canonical.findIndex(p=>p[0]*sign>.10&&p[1]>.025&&p[1]<.07),visited=new Set([start]),pending=[start];let found=false;while(pending.length){const n=pending.pop(),p=canonical[n];if(p&&p[0]*sign>.10&&p[1]>.32&&p[1]<.45){found=true;break}for(const next of adjacency.get(n)||[])if(!visited.has(next)){visited.add(next);pending.push(next)}}connected.push(found)}
 // Reproduce the old exposed ankle cut on this same source geometry. The new
 // check must distinguish that defective construction from a continuous limb.
 const oldCut=faces.filter(face=>face.every(id=>canonical[id][1]<.117)),oldEdges=edgesFor(oldCut);let oldOpenAnkleEdges=0;
 for(const [key,count] of oldEdges){if(count!==1)continue;const [a,b]=key.split(',').map(Number);if(isAnkle(a,b))oldOpenAnkleEdges++}
 return {openAnkleEdges,oldOpenAnkleEdges,footToCalfConnected:connected,nativeVertices:canonical.length,triangles:faces.length};
}
