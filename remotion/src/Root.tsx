import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {Video} from './compositions/Video';
import {Case3D, MaterialTune, View} from './components/Case3D';
import {loadFonts} from './fonts';
import type {VideoProps} from './types';

loadFonts();

const meta: CalculateMetadataFunction<VideoProps> = ({props}) => ({
  durationInFrames: props.durationInFrames,
  fps: props.fps,
});

const demo: VideoProps = {
  template: 'p_one_line',
  style: 'premium',
  fps: 30,
  durationInFrames: 90,
  clips: [],
  screens: [{from: 0, durationInFrames: 60, text: 'Introducing Plaire.', eyebrow: 'PLAIRE', animateIn: false}],
  textColor: 'white',
  endFrame: null,
};

type ModelStillProps = {model: string; view: View; tune?: MaterialTune};
const ModelStill: React.FC<ModelStillProps> = ({model, view, tune}) => (
  <Case3D src={model} scene="view" total={1} view={view} tune={tune} />
);

// Шаблоны фазы 1. Новый шаблон = новая Composition + функция в planner/templates.py.
export const Root: React.FC = () => (
  <>
    <Composition id="p-one-line" component={Video} width={1080} height={1920} fps={30} durationInFrames={90}
      defaultProps={demo} calculateMetadata={meta} />
    <Composition id="n-statement" component={Video} width={1080} height={1920} fps={30} durationInFrames={90}
      defaultProps={{...demo, template: 'n_statement', style: 'native'}} calculateMetadata={meta} />
    <Composition id="model-still" component={ModelStill} width={1080} height={1920} fps={30} durationInFrames={30}
      defaultProps={{model: 'models/black.glb', view: 'three_quarter' as View}} />
  </>
);
