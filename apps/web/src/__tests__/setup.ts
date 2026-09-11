// Vitest test setup file
const storageMock: Record<string, string> = {};
const localStorageMock = {
  getItem: (key: string) => storageMock[key] ?? null,
  setItem: (key: string, value: string) => {
    storageMock[key] = value;
  },
  removeItem: (key: string) => {
    delete storageMock[key];
  },
  clear: () => {
    for (const k of Object.keys(storageMock)) delete storageMock[k];
  },
  length: 0,
  key: () => null,
};

(global as any).localStorage = localStorageMock;
if (typeof (global as any).window === 'undefined') {
  (global as any).window = {
    localStorage: localStorageMock,
    dispatchEvent: () => true,
    location: { origin: 'http://localhost:3000' },
  };
} else {
  (global as any).window.localStorage = localStorageMock;
}
