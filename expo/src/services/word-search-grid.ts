// Browser-side equivalent of the worksheet export's source word-search grid fallback.
export function makeWordSearchGrid(rawWords: unknown[]): string[][] {
  const words = [...new Set(rawWords.map((value) => String(value || '').replace(/\(.*?\)/g, '').split(/\s[-–—]\s|,/)[0].toLocaleUpperCase().replace(/[^A-ZÁÉÍÓÚÜÑÇĞİÖŞ0-9]/g, '')).filter((word) => word.length >= 2))].sort((a, b) => b.length - a.length).slice(0, 12);
  if (!words.length) return [];
  const size = Math.max(10, words[0].length + 2, Math.ceil(Math.sqrt(words.reduce((sum, word) => sum + word.length, 0))) + 3, words.length + 3);
  const directions = [[0, 1], [1, 0], [1, 1], [-1, 1]];
  let seed = 2166136261;
  for (const char of words.join('|')) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619) >>> 0;
  const next = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const grid = Array.from({ length: size }, () => Array<string>(size).fill(''));
  for (const word of words) {
    let placed = false;
    for (let attempt = 0; attempt < 500 && !placed; attempt += 1) {
      const [dr, dc] = directions[Math.floor(next() * directions.length)];
      const row = Math.floor(next() * size);
      const col = Math.floor(next() * size);
      const endRow = row + dr * (word.length - 1);
      const endCol = col + dc * (word.length - 1);
      if (endRow < 0 || endRow >= size || endCol < 0 || endCol >= size) continue;
      if ([...word].some((char, index) => grid[row + dr * index][col + dc * index] && grid[row + dr * index][col + dc * index] !== char)) continue;
      [...word].forEach((char, index) => { grid[row + dr * index][col + dc * index] = char; });
      placed = true;
    }
    if (!placed) return [];
  }
  const alphabet = [...new Set(`ABCDEFGHIJKLMNOPQRSTUVWXYZ${words.join('')}`)];
  for (const row of grid) for (let column = 0; column < size; column += 1) if (!row[column]) row[column] = alphabet[Math.floor(next() * alphabet.length)];
  return grid;
}
