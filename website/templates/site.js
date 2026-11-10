const button=document.querySelector('.menu-button');const nav=document.querySelector('.site-nav');if(button&&nav){button.addEventListener('click',()=>{const open=nav.classList.toggle('is-open');button.setAttribute('aria-expanded',String(open))});nav.addEventListener('click',()=>{nav.classList.remove('is-open');button.setAttribute('aria-expanded','false')})}

// Safari may keep wheel gestures on the outer page after the pointer enters an
// iframe. A non-passive outer listener also keeps that region on the event path.
const relationshipGraph=document.querySelector('iframe[src^="/tree/graph/app/genealogy_relationship_graph.html"]');
if(relationshipGraph){
  window.addEventListener('wheel',event=>{
    if(event.defaultPrevented||document.elementFromPoint(event.clientX,event.clientY)!==relationshipGraph)return;
    const bounds=relationshipGraph.getBoundingClientRect();
    const x=event.clientX-bounds.left-relationshipGraph.clientLeft;
    const y=event.clientY-bounds.top-relationshipGraph.clientTop;
    const graphDocument=relationshipGraph.contentDocument;
    const graph=graphDocument?.getElementById('cy');
    if(!graph||!graph.contains(graphDocument.elementFromPoint(x,y)))return;
    const forwarded=new relationshipGraph.contentWindow.WheelEvent('wheel',{
      bubbles:true,cancelable:true,clientX:x,clientY:y,
      deltaX:event.deltaX,deltaY:event.deltaY,deltaZ:event.deltaZ,deltaMode:event.deltaMode,
      ctrlKey:event.ctrlKey,shiftKey:event.shiftKey,altKey:event.altKey,metaKey:event.metaKey
    });
    graph.dispatchEvent(forwarded);
    if(forwarded.defaultPrevented){
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },{capture:true,passive:false});
}
