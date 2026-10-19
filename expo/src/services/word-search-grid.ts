// Browser-side equivalent of the worksheet export's source word-search grid fallback.
export type WordSearchPlacement = { word: string; start: [number, number]; end: [number, number] };
export function makeWordSearchPuzzle(rawWords: unknown[]): { grid: string[][]; placements: WordSearchPlacement[] } {
  const words = [...new Set(rawWords.map((value) => String(value || '').replace(/\(.*?\)/g, '').split(/\s[-–—]\s|,/)[0].toLocaleUpperCase().replace(/[^A-ZÁÉÍÓÚÜÑÇĞİÖŞ0-9]/g, '')).filter((word) => word.length >= 2))].sort((a, b) => b.length - a.length).slice(0, 12);
  if (!words.length) return { grid: [], placements: [] };
  const size = Math.max(10, words[0].length + 2, Math.ceil(Math.sqrt(words.reduce((sum, word) => sum + word.length, 0))) + 3, words.length + 3);
  const directions = [[0, 1], [1, 0], [1, 1], [-1, 1]];
  let seed = 2166136261;
  for (const char of words.join('|')) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619) >>> 0;
  const next = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const grid = Array.from({ length: size }, () => Array<string>(size).fill(''));
  const placements: WordSearchPlacement[] = [];
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
      placements.push({ word, start: [row, col], end: [endRow, endCol] });
      placed = true;
    }
    if (!placed) return { grid: [], placements: [] };
  }
  const alphabet = [...new Set(`ABCDEFGHIJKLMNOPQRSTUVWXYZ${words.join('')}`)];
  for (const row of grid) for (let column = 0; column < size; column += 1) if (!row[column]) row[column] = alphabet[Math.floor(next() * alphabet.length)];
  return { grid, placements };
}

export function makeWordSearchGrid(rawWords: unknown[]): string[][] {
  return makeWordSearchPuzzle(rawWords).grid;
}

export function findWordSearchPlacements(grid: string[][], rawWords: unknown[]): WordSearchPlacement[] {
  const normalize = (value: unknown) => String(value || '').toLocaleUpperCase().replace(/[^A-ZÁÉÍÓÚÜÑÇĞİÖŞ0-9]/g, '');
  const directions = [[0, 1], [1, 0], [1, 1], [-1, 1], [0, -1], [-1, 0], [-1, -1], [1, -1]];
  const words = [...new Set(rawWords.map((value) => normalize(String(value || '').replace(/\(.*?\)/g, '').split(/\s[-–—]\s|,/)[0])).filter((word) => word.length >= 2))];
  return words.flatMap((word) => {
    for (let row = 0; row < grid.length; row += 1) for (let column = 0; column < grid[row].length; column += 1) {
      for (const [dr, dc] of directions) {
        const endRow = row + dr * (word.length - 1);
        const endColumn = column + dc * (word.length - 1);
        if (endRow < 0 || endRow >= grid.length || endColumn < 0 || endColumn >= (grid[endRow]?.length || 0)) continue;
        if ([...word].every((letter, index) => normalize(grid[row + dr * index]?.[column + dc * index]) === letter)) return [{ word, start: [row, column] as [number, number], end: [endRow, endColumn] as [number, number] }];
      }
    }
    return [];
  });
}
