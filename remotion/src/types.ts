export type TextColor = 'ink' | 'white';

export type ClipSpec = {
  src: string;              // путь в public/, например clips/c0.mp4
  from: number;             // кадр начала на таймлайне
  durationInFrames: number; // включая перекрытие для dissolve
  pushIn?: [number, number];// масштаб в начале и в конце плана (премиум)
  dissolveInFrames?: number;// плавный вход поверх предыдущего плана
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
