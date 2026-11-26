// Единственный источник фактов, цветов и сетки — brand.json в корне репозитория.
import brandJson from '../../brand.json';

export const brand = brandJson;
export const palette = brandJson.palette;
export const type = brandJson.type;
export const safe = brandJson.safe_zone_9x16;
export const motion = brandJson.motion;
export const effects = brandJson.effects;
export const FONT = `'${brandJson.type.font}', sans-serif`;

export const W = 1080;
export const H = 1920;
// зона текста 9:16: x 120…960, y 270…1248 (ниже y 840 справа колонка кнопок)
export const TEXT_LEFT = safe.side;
export const TEXT_RIGHT = W - safe.side;
export const TEXT_TOP = safe.top;
export const TEXT_BOTTOM = H - safe.bottom;
export const RAIL_RIGHT = W - safe.right_buttons.width;
