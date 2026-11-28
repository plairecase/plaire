import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
// 3D (модель чехла) на машинах без видеокарты: программный WebGL
Config.setChromiumOpenGlRenderer('swangle');
