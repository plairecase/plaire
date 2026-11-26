import {continueRender, delayRender, staticFile} from 'remotion';
import {brand} from './brand';

const FACES = [
  {file: 'fonts/TikTokSans-300-normal.ttf', weight: '300', stretch: '100%'},
  {file: 'fonts/TikTokSans-400-normal.ttf', weight: '400', stretch: '100%'},
  {file: 'fonts/TikTokSans-500-normal.ttf', weight: '500', stretch: '100%'},
  {file: 'fonts/TikTokSans-500-expanded.ttf', weight: '500', stretch: '125%'},
  {file: 'fonts/TikTokSans-600-normal.ttf', weight: '600', stretch: '100%'},
];

let started = false;
export const loadFonts = () => {
  if (started || typeof document === 'undefined') return;
  started = true;
  const handle = delayRender('TikTok Sans');
  Promise.all(
    FACES.map((f) =>
      new FontFace(brand.type.font, `url(${staticFile(f.file)}) format('truetype')`, {
        weight: f.weight,
        stretch: f.stretch,
      })
        .load()
        .then((ff) => document.fonts.add(ff)),
    ),
  )
    .then(() => continueRender(handle))
    .catch((e) => {
      // без шрифта рендер не продолжаем: другой шрифт запрещён
      throw new Error('Не загрузился TikTok Sans: ' + e);
    });
};
