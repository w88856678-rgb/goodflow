import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Composition,
  Easing,
  Img,
  Sequence,
  getInputProps,
  interpolate,
  registerRoot,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const W = 1080;
const H = 1920;
const FPS = 30;
const COLORS = {
  cream: '#F2E7CE',
  ink: '#18211D',
  red: '#D9543F',
  yellow: '#F3C85A',
  green: '#2D6B55',
  blue: '#335D73',
  coral: '#E66A4B',
};

const clamp = (v) => Math.max(0, Math.min(1, v));
const sec = (value) => Math.round(value * FPS);
const safeBox = (layout, fallback) => layout ? {
  left: layout.x,
  top: layout.y,
  width: layout.width,
  maxWidth: layout.width,
  right: 'auto',
  bottom: 'auto',
} : fallback;

const defaults = {
  projectName: '公益项目',
  organization: '',
  duration: 30,
  fps: FPS,
  scenes: [],
  captions: [],
  narration: null,
  music: null,
  sfx: [],
  cta: '',
  facts: {numbers: []},
};

const camera = (local, duration, move) => {
  const ease = Easing.inOut(Easing.cubic);
  const p = interpolate(local, [0, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });
  if (move === 'pull_out') return `scale(${1.15 - p * 0.09})`;
  if (move === 'pan') return `translateX(${-42 + p * 74}px) scale(1.11)`;
  if (move === 'rise') return `translateY(${38 - p * 72}px) scale(1.12)`;
  if (move === 'parallax') return `translate(${22 - p * 42}px, ${14 - p * 26}px) scale(${1.08 + p * 0.045})`;
  if (move === 'static') return 'scale(1.06)';
  return `translateY(${16 - p * 28}px) scale(${1.06 + p * 0.10})`;
};

const PaperGrain = () => (
  <AbsoluteFill style={{
    pointerEvents: 'none',
    opacity: 0.13,
    mixBlendMode: 'multiply',
    backgroundImage: 'repeating-radial-gradient(circle at 20% 30%, rgba(20,20,10,.35) 0 1px, transparent 1px 4px)',
    backgroundSize: '7px 9px',
  }} />
);

const PaperWipe = ({local, color}) => {
  const p = spring({frame: local, fps: FPS, config: {damping: 18, stiffness: 140, mass: 0.65}});
  return <AbsoluteFill style={{
    backgroundColor: color,
    transform: `translateX(${interpolate(p, [0, 1], [-5, 112])}%) rotate(-1.5deg)`,
    clipPath: 'polygon(0 0,92% 0,100% 4%,94% 11%,100% 18%,93% 28%,100% 36%,95% 47%,100% 58%,93% 69%,100% 82%,94% 91%,100% 100%,0 100%)',
    zIndex: 30,
  }} />;
};

const HeadlineStrip = ({local, text}) => {
  const p = spring({frame: local - 7, fps: FPS, config: {damping: 14, stiffness: 145}});
  return <div style={{
    position: 'absolute', left: 58, top: 120, maxWidth: 850,
    padding: '18px 30px 20px', background: COLORS.cream, color: COLORS.ink,
    fontFamily: '"PingFang SC",sans-serif', fontWeight: 950, fontSize: 58,
    boxShadow: '14px 16px 0 rgba(20,25,20,.25)',
    transform: `translateX(${interpolate(p, [0, 1], [-680, 0])}px) rotate(-2deg)`,
    clipPath: 'polygon(1% 4%,98% 0,100% 88%,4% 100%,0 30%)',
  }}>{text}</div>;
};

const Steam = ({local, x = 360, y = 720}) => (
  <svg width="300" height="360" viewBox="0 0 300 360" style={{position: 'absolute', left: x, top: y, opacity: .75}}>
    {[0, 1, 2].map((i) => {
      const rise = (local * (1.8 + i * .2)) % 130;
      const sway = Math.sin(local / 11 + i * 1.7) * 18;
      return <path key={i} d={`M ${65+i*70+sway} ${315-rise} C ${30+i*65} ${250-rise}, ${115+i*55} ${205-rise}, ${70+i*70+sway} ${145-rise}`}
        fill="none" stroke={COLORS.cream} strokeWidth="11" strokeLinecap="round" opacity={.38+i*.16} />;
    })}
  </svg>
);

const StatBadges = ({local, facts}) => {
  const nums = (facts?.numbers || []).slice(0, 3);
  return <>{nums.map((item, i) => {
    const p = spring({frame: local - 8 - i * 7, fps: FPS, config: {damping: 12, stiffness: 160}});
    return <div key={`${item.value}-${i}`} style={{
      position: 'absolute', left: 72 + i * 315, top: 1110 + (i % 2) * 90,
      width: 250, padding: '24px 20px', background: COLORS.cream, color: COLORS.ink,
      border: `7px solid ${[COLORS.red, COLORS.yellow, COLORS.green][i]}`,
      boxShadow: '12px 15px 0 rgba(20,25,20,.25)',
      transform: `scale(${p}) rotate(${[-5, 3, -2][i]}deg)`,
    }}>
      <div style={{fontSize: 72, lineHeight: .9, fontWeight: 950}}>{item.value}</div>
      <div style={{fontSize: 22, marginTop: 14, fontWeight: 800}}>项目关键数字</div>
    </div>;
  })}</>;
};

const RouteLine = ({local}) => {
  const p = interpolate(local, [8, 60], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  return <svg width="930" height="520" viewBox="0 0 930 520" style={{position: 'absolute', left: 72, top: 960}}>
    <path d="M40 410 C180 250,280 480,410 280 S690 80,880 140" fill="none"
      stroke={COLORS.yellow} strokeWidth="20" strokeLinecap="round"
      strokeDasharray="1400" strokeDashoffset={1400 * (1 - p)}
      style={{filter: 'drop-shadow(8px 10px 0 rgba(15,25,20,.25))'}} />
    <circle cx="40" cy="410" r="24" fill={COLORS.red} />
    <circle cx="880" cy="140" r={30 * p} fill={COLORS.cream} stroke={COLORS.red} strokeWidth="12" />
  </svg>;
};

const Clock = ({local}) => {
  const sweep = interpolate(local, [0, 90], [-110, 75], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  return <div style={{
    position: 'absolute', left: 690, top: 180, width: 240, height: 240,
    borderRadius: '50%', background: COLORS.cream, border: `14px solid ${COLORS.ink}`,
    boxShadow: '18px 22px 0 rgba(20,25,20,.22)', transform: `scale(${1+Math.sin(local/5)*.018}) rotate(-4deg)`,
  }}>
    <div style={{position: 'absolute', left: 108, top: 40, width: 15, height: 84, background: COLORS.red, transformOrigin: '8px 80px', transform: `rotate(${sweep}deg)`}} />
    <div style={{position: 'absolute', left: 110, top: 78, width: 13, height: 64, background: COLORS.ink, transformOrigin: '7px 40px', transform: 'rotate(150deg)'}} />
    <div style={{position: 'absolute', left: 101, top: 101, width: 32, height: 32, borderRadius: '50%', background: COLORS.red}} />
  </div>;
};

const RingFocus = ({local, target}) => {
  if (!target) return null;
  const p = spring({frame: local - 10, fps: FPS, config: {damping: 13, stiffness: 120}});
  return <div style={{
    position: 'absolute', left: target.x, top: target.y, width: target.width || 180, height: target.height || 180, borderRadius: '50%',
    border: `18px solid ${COLORS.cream}`, boxShadow: '20px 24px 0 rgba(20,20,15,.22)',
    transform: `scale(${interpolate(p, [0,1], [.2,1])}) rotate(${interpolate(p,[0,1],[-12,1])}deg)`,
  }} />;
};

const Arrow = ({local}) => {
  const p = spring({frame: local - 15, fps: FPS, config: {damping: 13, stiffness: 135}});
  return <div style={{
    position: 'absolute', left: 740, top: 620, color: COLORS.yellow, fontSize: 180, fontWeight: 950,
    textShadow: '10px 12px 0 rgba(20,25,20,.25)',
    transform: `translateX(${interpolate(p,[0,1],[220,0])}px) rotate(-20deg) scale(${p})`,
  }}>↙</div>;
};

const Starburst = ({local}) => {
  const p = spring({frame: local - 3, fps: FPS, config: {damping: 11, stiffness: 155}});
  return <div style={{
    position: 'absolute', left: 100, top: 420, width: 880, height: 880,
    background: `repeating-conic-gradient(${COLORS.yellow} 0 7deg,transparent 7deg 16deg)`,
    borderRadius: '50%', opacity: .5, transform: `scale(${p}) rotate(${local*.12}deg)`,
    mixBlendMode: 'screen',
  }} />;
};

const Confetti = ({local}) => <>{Array.from({length: 28}).map((_, i) => {
  const x = (i * 193) % 1040;
  const y = ((local * (2.2 + i % 4)) + i * 97) % 2050 - 100;
  const rot = local * (2 + i % 5) + i * 23;
  return <div key={i} style={{
    position: 'absolute', left: x, top: y, width: 16 + i % 3 * 8, height: 45,
    background: [COLORS.red, COLORS.yellow, COLORS.green, COLORS.cream][i % 4],
    transform: `rotate(${rot}deg)`, boxShadow: '4px 5px 0 rgba(0,0,0,.16)',
  }} />;
})}</>;

const PhotoSlap = ({local}) => {
  const p = spring({frame: local - 8, fps: FPS, config: {damping: 12, stiffness: 145}});
  return <div style={{
    position: 'absolute', left: 105, top: 360, width: 360, height: 500,
    border: `12px solid ${COLORS.cream}`, boxShadow: '18px 22px 0 rgba(20,25,20,.25)',
    transform: `translateY(${interpolate(p,[0,1],[-700,0])}px) rotate(${interpolate(p,[0,1],[-18,-6])}deg)`,
  }} />;
};

const Timeline = ({frame, duration}) => (
  <div style={{position: 'absolute', left: 52, top: 72, zIndex: 40, color: COLORS.cream, fontFamily: 'Arial,sans-serif'}}>
    <div style={{fontSize: 20, fontWeight: 800, letterSpacing: 4}}>PUBLIC GOOD · STORY</div>
    <div style={{width: 200, height: 7, background: COLORS.red, marginTop: 14}}>
      <div style={{width: `${clamp(frame/duration)*100}%`, height: '100%', background: COLORS.yellow}} />
    </div>
  </div>
);

const QuoteCard = ({local, text, layout}) => {
  const p = spring({frame: local - 8, fps: FPS, config: {damping: 16, stiffness: 110}});
  return <div style={{
    position: 'absolute', ...safeBox(layout, {left: 120, top: 300, width: 780}), padding: '52px 48px',
    background: 'rgba(242,231,206,.95)', color: COLORS.ink, fontSize: 54, lineHeight: 1.25,
    fontFamily: '"Songti SC","PingFang SC",serif', fontWeight: 900,
    boxShadow: '20px 24px 0 rgba(20,25,20,.24)',
    transform: `translateY(${interpolate(p,[0,1],[160,0])}px) rotate(-2deg)`,
  }}>“{text}”</div>;
};

const PhotoWall = ({local}) => <>{[-9, 6, -3].map((rot, i) => {
  const p = spring({frame: local - 8 - i * 6, fps: FPS, config: {damping: 15, stiffness: 115}});
  return <div key={i} style={{
    position: 'absolute', left: 95 + i * 290, top: 1000 + (i % 2) * 110,
    width: 300, height: 430, border: `11px solid ${COLORS.cream}`,
    boxShadow: '16px 19px 0 rgba(20,25,20,.22)',
    transform: `translateY(${interpolate(p,[0,1],[380,0])}px) rotate(${rot}deg) scale(${p})`,
  }} />;
})}</>;

const CtaCard = ({local, text, layout}) => {
  const p = spring({frame: local - 8, fps: FPS, config: {damping: 16, stiffness: 120}});
  return <div style={{
    position: 'absolute', ...safeBox(layout, {left: 90, bottom: 340, width: 900}), padding: '48px 42px',
    background: COLORS.red, color: COLORS.cream, textAlign: 'center', fontSize: 62,
    fontFamily: '"PingFang SC",sans-serif', fontWeight: 950,
    boxShadow: '18px 22px 0 rgba(20,25,20,.25)',
    transform: `scale(${p}) rotate(-1deg)`,
  }}>{text || '让真实的改变被更多人看见'}</div>;
};

const LayeredBackdrop = ({scene, local, duration}) => {
  const base = camera(local, duration, scene.move);
  const p = interpolate(local, [0, duration], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const common = {
    position: 'absolute', width: '100%', height: '100%',
    objectFit: 'cover', filter: 'saturate(1.04) contrast(1.025)',
  };
  const layers = scene.layers;
  if (scene.depth === 'layered' && layers?.background && layers?.subject) {
    return <AbsoluteFill>
      <Img src={staticFile(layers.background)} style={{...common, transform: `${base} scale(1.025)`}} />
      <Img src={staticFile(layers.subject)} style={{
        ...common, objectFit: 'fill',
        transform: `${base} translate(${12-p*24}px, ${7-p*14}px) scale(1.012)`,
      }} />
      {layers.foreground ? <Img src={staticFile(layers.foreground)} style={{
        ...common, objectFit: 'fill',
        transform: `${base} translate(${-9+p*18}px, ${13-p*26}px) scale(1.024)`,
      }} /> : null}
    </AbsoluteFill>;
  }
  return <AbsoluteFill>
    <Img src={staticFile(scene.file)} style={{...common, transform: base}} />
  </AbsoluteFill>;
};

const PinDrop = ({local, target}) => {
  if (!target) return null;
  const p = spring({frame: local, fps: FPS, config: {damping: 10, stiffness: 190, mass: .55}});
  return <div style={{
    position: 'absolute', left: target.x, top: target.y, width: 104, height: 104,
    borderRadius: '52% 52% 52% 8%', background: COLORS.red,
    border: `10px solid ${COLORS.cream}`, boxShadow: '16px 19px 0 rgba(20,25,20,.25)',
    transform: `translateY(${interpolate(p,[0,1],[-640,0])}px) rotate(-45deg) scale(${.35+.65*p})`,
    transformOrigin: '50% 50%',
  }}><div style={{
    position: 'absolute', width: 30, height: 30, borderRadius: '50%',
    background: COLORS.cream, left: 27, top: 27,
  }} /></div>;
};

const Underline = ({local, text, layout}) => {
  const p = interpolate(local, [0, 26], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  return <div style={{
    position: 'absolute', ...safeBox(layout, {left: 90, top: 1220, maxWidth: 820}),
    color: COLORS.cream, fontFamily: '"PingFang SC",sans-serif',
    fontWeight: 950, fontSize: 54, textShadow: '5px 7px 0 rgba(20,25,20,.32)',
  }}>
    {text}
    <div style={{
      height: 18, width: `${p*100}%`, background: COLORS.yellow,
      marginTop: 10, transform: 'rotate(-1deg)', boxShadow: '7px 8px 0 rgba(20,25,20,.2)',
    }} />
  </div>;
};

const NumberCard = ({local, value, layout}) => {
  const p = spring({frame: local, fps: FPS, config: {damping: 12, stiffness: 145}});
  return <div style={{
    position: 'absolute', ...safeBox(layout, {right: 72, top: 920, minWidth: 270}),
    padding: '30px 34px', background: COLORS.cream, color: COLORS.ink,
    border: `10px solid ${COLORS.red}`, boxShadow: '17px 20px 0 rgba(20,25,20,.26)',
    transform: `translateX(${interpolate(p,[0,1],[420,0])}px) rotate(3deg)`,
    fontFamily: '"PingFang SC",sans-serif', fontWeight: 950, fontSize: 74,
    textAlign: 'center',
  }}>{value}</div>;
};

const FactStack = ({local, items = [], variant = '', layout}) => (
  <div style={{position: 'absolute', ...safeBox(layout, {left: 72, top: 900, width: 936}), display: 'flex', flexWrap: 'wrap', gap: 18}}>
    {items.map((item, index) => {
      const p = spring({frame: local - index * 5, fps: FPS, config: {damping: 14, stiffness: 145}});
      return <div key={`${item}-${index}`} style={{
        width: variant === 'people' ? 450 : 'auto', padding: '18px 26px 20px',
        color: COLORS.ink, background: 'rgba(242,231,206,.97)', fontSize: 43,
        lineHeight: 1.08, fontWeight: 900, boxShadow: '10px 12px 0 rgba(20,25,20,.24)',
        opacity: p, transform: `translateY(${interpolate(p,[0,1],[55,0])}px) rotate(${interpolate(p,[0,1],[-2,0])}deg)`,
      }}>{item}</div>;
    })}
  </div>
);

const CauseFlow = ({local, items = [], layout}) => (
  <div style={{position: 'absolute', ...safeBox(layout, {left: 70, top: 825, width: 940}), display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18}}>
    {items.slice(0, 3).map((item, index) => {
      const p = spring({frame: local - index * 5, fps: FPS, config: {damping: 14, stiffness: 145}});
      return <div key={`${item}-${index}`} style={{
        minHeight: 220, padding: '28px 22px 24px', color: COLORS.ink,
        background: 'rgba(242,231,206,.97)', boxShadow: '12px 15px 0 rgba(20,25,20,.24)',
        fontSize: 42, lineHeight: 1.12, fontWeight: 900, textAlign: 'center', opacity: p,
        transform: `translateY(${interpolate(p,[0,1],[55,0])}px)`,
      }}><div style={{marginBottom: 18, color: COLORS.red, fontSize: 30, letterSpacing: 2}}>0{index + 1}</div>{item}</div>;
    })}
  </div>
);

const ArrowIn = ({local, target}) => {
  if (!target) return null;
  const p = spring({frame: local, fps: FPS, config: {damping: 12, stiffness: 155}});
  return <div style={{
    position: 'absolute', left: target.x, top: target.y, color: COLORS.yellow,
    fontSize: 210, fontWeight: 950, textShadow: '10px 12px 0 rgba(20,25,20,.24)',
    transform: `translate(${interpolate(p,[0,1],[280,0])}px,${interpolate(p,[0,1],[-120,0])}px) rotate(-26deg) scale(${p})`,
  }}>↙</div>;
};

const SceneEvent = ({event, local, duration, props}) => {
  if (event.suppressed) return null;
  const start = Math.round(duration * Number(event.at || 0));
  const eventLocal = local - start;
  if (eventLocal < 0) return null;
  if (event.type === 'paper_label') return <HeadlineStrip local={eventLocal + 7} text={event.text || ''} />;
  if (event.type === 'route_draw') return <RouteLine local={eventLocal + 8} />;
  if (event.type === 'pin_drop') return <PinDrop local={eventLocal} target={event.target} />;
  if (event.type === 'focus_ring') return <RingFocus local={eventLocal + 10} target={event.target} />;
  if (event.type === 'number_card') return <NumberCard local={eventLocal} value={event.value || ''} layout={event.layout} />;
  if (event.type === 'underline') return <Underline local={eventLocal} text={event.text || ''} layout={event.layout} />;
  if (event.type === 'fact_stack') return <FactStack local={eventLocal} items={event.items || []} variant={event.variant || ''} layout={event.layout} />;
  if (event.type === 'cause_flow') return <CauseFlow local={eventLocal} items={event.items || []} layout={event.layout} />;
  if (event.type === 'arrow_in') return <ArrowIn local={eventLocal} target={event.target} />;
  if (event.type === 'steam_rise') return <Steam local={eventLocal} />;
  if (event.type === 'quote_reveal') return <QuoteCard local={eventLocal + 8} text={event.text || ''} layout={event.layout} />;
  if (event.type === 'cta_reveal') return <CtaCard local={eventLocal + 8} text={props.cta} layout={event.layout} />;
  return null;
};

const SceneTransition = ({local, type, color}) => {
  if (type === 'paper_wipe') return <PaperWipe local={local} color={color} />;
  const p = spring({frame: local, fps: FPS, config: {damping: 18, stiffness: 135, mass: .7}});
  if (type === 'paper_roll') return <AbsoluteFill style={{
    zIndex: 35, background: COLORS.cream,
    transform: `translateY(${interpolate(p,[0,1],[0,-108])}%)`,
    boxShadow: '0 28px 38px rgba(20,20,15,.25)',
  }} />;
  if (type === 'ink_reveal') return <AbsoluteFill style={{
    zIndex: 35, background: COLORS.ink,
    clipPath: `circle(${interpolate(p,[0,1],[86,0])}% at 50% 50%)`,
  }} />;
  return <AbsoluteFill style={{
    zIndex: 35, background: color,
    transform: `translateX(${interpolate(p,[0,1],[0,-108])}%) skewX(-3deg)`,
    boxShadow: '28px 0 38px rgba(20,20,15,.25)',
  }} />;
};

const renderComponent = (name, ctx) => {
  const {local, frame, scene, props} = ctx;
  const title = props.captions.find((c) => sec(c.from) >= sec(scene.start) && sec(c.from) < sec(scene.end))?.text || props.projectName;
  if (name === 'headline_strip') return <HeadlineStrip key={name} local={local} text={title} />;
  if (name === 'stat_badges') return <StatBadges key={name} local={local} facts={props.facts} />;
  if (name === 'route_line') return <RouteLine key={name} local={local} />;
  if (name === 'clock') return <Clock key={name} local={local} />;
  if (name === 'steam') return <Steam key={name} local={local} />;
  if (name === 'photo_slap') return <PhotoSlap key={name} local={local} />;
  if (name === 'ring_focus') return <RingFocus key={name} local={local} />;
  if (name === 'arrow') return <Arrow key={name} local={local} />;
  if (name === 'confetti') return <Confetti key={name} local={local} />;
  if (name === 'starburst') return <Starburst key={name} local={local} />;
  if (name === 'timeline') return <Timeline key={name} frame={frame} duration={sec(props.duration)} />;
  if (name === 'quote_card') return <QuoteCard key={name} local={local} text={title} />;
  if (name === 'photo_wall') return <PhotoWall key={name} local={local} />;
  if (name === 'cta_card') return <CtaCard key={name} local={local} text={props.cta} />;
  return null;
};

const Scene = ({scene, index, props}) => {
  const frame = useCurrentFrame();
  const start = sec(scene.start);
  const end = sec(scene.end);
  if (frame < start || frame >= end) return null;
  const local = frame - start;
  const duration = end - start;
  const fadeIn = clamp(local / 12);
  const fadeOut = index === props.scenes.length - 1 ? 1 : clamp((end - frame) / 12);
  return <AbsoluteFill style={{opacity: Math.min(fadeIn, fadeOut), background: scene.accent, overflow: 'hidden'}}>
    <LayeredBackdrop scene={scene} local={local} duration={duration} />
    <AbsoluteFill style={{background: 'linear-gradient(180deg,transparent 52%,rgba(15,20,16,.13) 100%)'}} />
    {(scene.motion_components || []).map((name) => renderComponent(name, {local, frame, scene, props}))}
    {(scene.motion_events || []).map((event, eventIndex) =>
      <SceneEvent key={`${event.type}-${eventIndex}`} event={event} local={local} duration={duration} props={props} />
    )}
    {index > 0 ? <SceneTransition local={local} type={scene.transition} color={scene.accent} /> : null}
  </AbsoluteFill>;
};

const Caption = ({props}) => {
  const frame = useCurrentFrame();
  const cap = props.captions.find((c) => frame >= sec(c.from) && frame < sec(c.to));
  if (!cap) return null;
  if (cap.lines !== undefined && (!Array.isArray(cap.lines) || !cap.lines.length || cap.lines.some(line => typeof line !== 'string' || !line || line.includes('\n')) || cap.lines.join('') !== cap.text)) {
    throw new Error('Caption lines must match the exact approved text.');
  }
  const p = interpolate(frame - sec(cap.from), [0, 4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fontSize = cap.text.length > 54 ? 42 : (cap.text.length > 34 ? 44 : 48);
  return <div style={{
    position: 'absolute', left: '50%', bottom: 118, width: 'max-content', maxWidth: 960,
    transform: 'translateX(-50%)',
    opacity: p, padding: '20px 34px 22px', background: 'rgba(247,237,218,.97)',
    color: COLORS.ink, fontFamily: '"PingFang SC","Noto Sans CJK SC",sans-serif',
    fontSize, lineHeight: 1.3, fontWeight: 900, textAlign: 'center',
    boxShadow: '6px 8px 0 rgba(15,20,15,.20)', borderRadius: 3, zIndex: 60,
  }}>{cap.lines ? cap.lines.map((line, index) => <span key={index} style={{display: 'block', whiteSpace: 'nowrap'}}>{line}</span>) : cap.text}</div>;
};

const PublicGoodFilm = (input) => {
  const props = {...defaults, ...input};
  const frame = useCurrentFrame();
  const total = sec(props.duration);
  useVideoConfig();
  return <AbsoluteFill style={{background: COLORS.ink}}>
    {props.scenes.map((scene, i) => <Scene key={`${scene.id}-${scene.file}`} scene={scene} index={i} props={props} />)}
    <PaperGrain />
    <Caption props={props} />
    {props.narration ? <Audio src={staticFile(props.narration)} volume={.88} /> : null}
    {props.music ? <Audio loop src={staticFile(props.music)} volume={(f) =>
      interpolate(f, [0, 30, Math.max(31,total-70), total], [0, .10, .10, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
    } /> : null}
    {(props.sfx || []).map((item, index) =>
      <Sequence key={`${item.file}-${index}`} from={sec(item.from)} durationInFrames={45}>
        <Audio src={staticFile(item.file)} volume={item.volume || .2} />
      </Sequence>
    )}
  </AbsoluteFill>;
};

const Root = () => {
  const input = {...defaults, ...getInputProps()};
  return <Composition
    id="PublicGoodFilm"
    component={PublicGoodFilm}
    durationInFrames={sec(input.duration)}
    fps={FPS}
    width={W}
    height={H}
    defaultProps={input}
  />;
};

registerRoot(Root);
