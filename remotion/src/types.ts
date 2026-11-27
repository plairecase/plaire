export type TextColor = 'ink' | 'white';

export type TransitionType = 'cut' | 'zoom' | 'push' | 'whip' | 'punch' | 'impact';

export type Transition = {
  type: TransitionType;
  frames: number;           // длительность перехода (для zoom/push/whip = перекрытие планов)
};

export type ClipSpec = {
  src: string;              // путь в public/, например clips/c0.mp4
  from: number;             // кадр начала на таймлайне
  durationInFrames: number; // включая перекрытие для перехода
  pushIn?: [number, number];// масштаб в начале и в конце плана (премиум)
  transitionIn?: Transition;
  transitionOut?: Transition;
};

export type TextScreen = {
  from: number;
  durationInFrames: number;
  text: string;
  eyebrow?: string;
  animateIn: boolean;       // первый экран = обложка, виден с кадра 0
};

export type EndFrameSpec = {
  from: number;
  durationInFrames: number;
  color: TextColor;
  eyebrow: string;
  price: string;
  site: string;
  shipping: string;
  tagTop?: number;          // y ценника: ниже чехла, выше 1248
};

export type VideoProps = {
  template: string;
  style: 'premium' | 'native';
  fps: number;
  durationInFrames: number;
  clips: ClipSpec[];
  screens: TextScreen[];
  textColor: TextColor;
  endFrame?: EndFrameSpec | null;
};
