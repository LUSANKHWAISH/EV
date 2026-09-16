import QtQuick
Canvas {
    id:chart
    property var samples:[]
    property color lineColor:'#c69a52'
    property real maximum:100
    onSamplesChanged:requestPaint()
    onWidthChanged:requestPaint()
    onHeightChanged:requestPaint()
    onPaint:{
        let c=getContext('2d');c.reset();c.strokeStyle='#1c2b32';c.lineWidth=1
        for(let i=1;i<4;i++){let y=height*i/4;c.beginPath();c.moveTo(0,y);c.lineTo(width,y);c.stroke()}
        if(samples.length<2)return
        c.beginPath()
        for(let i=0;i<samples.length;i++){let x=width*i/Math.max(47,samples.length-1);let y=height-4-Math.min(1,samples[i]/maximum)*(height-8);if(i===0)c.moveTo(x,y);else c.lineTo(x,y)}
        c.strokeStyle=lineColor;c.lineWidth=1.25;c.stroke()
    }
}
