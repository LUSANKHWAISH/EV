VARYING vec2 vUv;
VARYING vec3 vWorld;
VARYING vec3 vNormal;
VARYING vec3 vLocal;

float hash21(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float packet(float u,float head) {
    float d=u-head;
    return exp(-d*d*4800.0)+.46*exp(min(d,0.0)*24.0)*(1.0-smoothstep(0.0,.015,d));
}
void MAIN() {
    if(kind==6) {
        vec2 p=(vUv-.5)*2.0;
        float spot=exp(-dot(p,p)*24.0);
        float ray=exp(-abs(p.x)*75.0-abs(p.y)*4.0)+exp(-abs(p.y)*95.0-abs(p.x)*3.5);
        float fade=smoothstep(0.0,.035,deployment)*(1.0-smoothstep(.38,.68,deployment));
        FRAGCOLOR=vec4(vec3(1.0,.84,.4),min(.95,(spot+ray*.35)*fade*gain));
        return;
    }
    if(kind==7) {
        float head=smoothstep(.03,.38,deployment);
        float cross=pow(max(0.0,1.0-abs(vUv.y*2.0-1.0)),.5);
        float tail=packet(vUv.x,head)*cross*(1.0-smoothstep(.35,.52,deployment));
        FRAGCOLOR=vec4(vec3(1.0,.69,.15),min(.95,tail*gain));
        return;
    }
    if(kind==8) {
        // Shared lane/phase keeps each fork attached to its parent's discharge.
        float lane=floor(vUv.x);float u=fract(vUv.x)/.98;
        float h=hash21(vec2(lane,43.0));
        float age=fract(timeSeconds*(.48+h*.3)+h*19.0);
        float life=smoothstep(.005,.025,age)*(1.0-smoothstep(.17,.31,age));
        float beatArc=beatPulse*step(h,.22);
        life=max(life,beatArc);
        float head=age*7.2;
        float wake=smoothstep(u-.045,u+.045,head)*exp(-max(0.0,head-u)*2.7);
        wake=max(wake,beatArc);
        float snap=.72+.28*pow(.5+.5*sin(age*280.0+h*32.0),2.0);
        float y=abs(vUv.y*2.0-1.0);
        float spine=exp(-y*y*125.0);
        float corona=exp(-y*y*9.0)*.24;
        float alpha=(spine+corona)*life*wake*snap*coverage*(1.0+reaction*.7);
        vec3 fire=mix(vec3(1.0,.39,.018),vec3(1.0,.90,.45),spine);
        FRAGCOLOR=vec4(fire*min(gain,2.3),min(.98,alpha*2.6)*smoothstep(.55,.86,deployment));
        return;
    }
    float facing=dot(normalize(vNormal),normalize(CAMERA_POSITION-vWorld));
    float edge=pow(1.0-clamp(abs(facing),0.0,1.0),2.0);
    vec4 flow=texture(flowMap,vUv+vec2(timeSeconds*.012+seed,0.0));
    float activation=pow(.5+.5*sin(flow.b*13.0-timeSeconds*1.15+seed*5.0),4.0);
    vec2 dataUv=vUv;
    if(kind==1) dataUv.x-=timeSeconds*.021;
    vec4 data=texture(detailMap,dataUv);
    float ink=mix(data.r,max(0.0,data.r-.18)*1.18,lowCost);
    float cell=hash21(floor(vUv*vec2(96.0,48.0))+seed);
    float age=fract(timeSeconds*(.28+cell*.3)+cell*11.0);
    float ignition=smoothstep(.03,.08,age)*(1.0-smoothstep(.1,.30,age));
    // Concentrated travelling response, masked by the existing traces. A
    // response brightens a passing region rather than flashing the whole ball.
    float sector=fract(atan(vLocal.y,vLocal.x)/6.2831853+.5+seed);
    float responseHead=fract(timeSeconds*.19+seed);
    float responseWave=packet(sector,responseHead)*reaction;
    float alpha;float brightness;float hot=data.b;
    if(kind==0) {
        float rear=facing<0.0?.4:1.0;
        alpha=(ink*1.12+data.g*.025+data.b*(.75+ignition*2.6))*coverage*rear*(.8+.7*edge);
        alpha*=.4+.6*data.a;
        brightness=.85+activation*.7+data.b*(1.0+ignition*3.0)+responseWave*1.7;
        alpha+=ink*responseWave*.4;
        hot=max(max(hot*.7,ignition*data.b),responseWave*.8);
    } else if(kind==1) {
        float wave=packet(fract(vUv.x*2.0+seed),fract(timeSeconds*.22+seed));
        float strand=pow(max(0.0,cos(vUv.y*151.0)),18.0);
        alpha=(.012+ink*1.2+strand*.11+data.b*(.9+ignition*1.6)+data.g*.025)*coverage;
        brightness=1.3+wave*(2.5+reaction*1.5)+activation*.65;
        hot=max(.32+data.b*.6,wave*(.85+reaction*.15));
        float opening=1.0-smoothstep(.55,.95,deployment);
        alpha*=1.0+opening*2.2;
        brightness+=opening*2.0;
        hot=max(hot,opening*.8);
    } else if(kind==2) {
        float cross=pow(max(0.0,1.0-abs(vUv.y*2.0-1.0)),.55);
        float wave=packet(fract(vUv.x),fract(timeSeconds*.36+seed));
        alpha=coverage*cross*(.32+.42*flow.b+wave*.75);
        brightness=1.2+1.4*activation+wave*(2.0+reaction*1.8);
        hot=.35+activation*.45+wave*.35;
    } else if(kind==4) {
        // Each strip is one filament, not a striped sheet. A branch inherits
        // its parent's lane and longitudinal coordinate so the light connects.
        float lane=floor(vUv.x);float u=fract(vUv.x)/.98;
        float h=hash21(vec2(lane,29.0));
        float cycle=fract(timeSeconds*(.32+h*.16)+h*11.0);
        float head=cycle*1.5-.18;
        float current=packet(u,head);
        current+=reaction*.5*packet(u,head-.24);
        float spine=pow(max(0.0,1.0-abs(vUv.y*2.0-1.0)),.48);
        float alive=smoothstep(0.0,.045,cycle)*(1.0-smoothstep(.90,1.0,cycle));
        alpha=coverage*spine*(.42+current*(1.7+reaction)*alive);
        brightness=1.4+current*(2.2+reaction);
        hot=.48+min(current,1.0)*.52;
    } else if(kind==5) {
        float lane=floor(vUv.x);float u=fract(vUv.x)/.98;
        float h=hash21(vec2(lane,17.0));
        float cycle=fract(timeSeconds*(.34+h*.19)+h*7.0);
        float head=cycle*1.55-.23;
        float pulse=packet(u,head);
        // Branches share their lane's phase; selected active paths get a second
        // packet, preserving a visible gap and a short falling tail.
        pulse+=reaction*step(h,.62)*packet(u,head-.27)*.75;
        float cross=pow(max(0.0,1.0-abs(vUv.y*2.0-1.0)),.6);
        float alive=smoothstep(0.0,.08,cycle)*(1.0-smoothstep(.84,1.0,cycle));
        alpha=coverage*cross*(.09+pulse*2.5)*alive*(facing<0.0?.75:1.0);
        brightness=.8+pulse*3.5;
        hot=.18+min(pulse,1.0)*.82;
    } else {
        float run=pow(.5+.5*sin(vUv.x*94.0-timeSeconds*3.1+seed),10.0);
        alpha=coverage*(.40+.32*activation+run*.65)*(facing<0.0?.40:1.0);
        brightness=.9+run*1.6;hot=.18+run*.7;
    }
    // Ordered assembly: an orbit sketches first, then circuits fill the volume.
    float azimuth=fract(atan(vLocal.y,vLocal.x)/6.2831853+.5);
    float threshold=kind==1?.16+azimuth*.28:kind==2?.12:.29+length(vLocal)/116.0*.30+cell*.12;
    alpha*=smoothstep(threshold,threshold+.14,deployment);
    float heat=clamp(hot+activation*.12,0.0,1.0);
    vec3 gold=mix(vec3(1.0,.30,.009),vec3(1.0,.66,.075),smoothstep(0.0,.7,heat));
    gold=mix(gold,vec3(1.0,.93,.52),smoothstep(.65,1.0,heat));
    float exposure=1.0-exp(-brightness*gain*1.25);
    vec3 rgb=pow(gold*exposure,vec3(.86));
    // Music-only attacks illuminate the hub and a few sharp current paths.
    // Zero pulse preserves the accepted Assistant rendering exactly.
    rgb*=1.0+beatPulse*(kind==2?1.7:kind==4?.7:.18);
    bool filament=kind==1 || kind==2 || kind==4;
    vec3 emission=filament?vec3(1.4,1.26,1.4):vec3(1.12);
    FRAGCOLOR=vec4(rgb*emission,clamp(alpha*(1.48+activation*.18),0.0,.97));
}
