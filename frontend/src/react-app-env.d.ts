/// <reference types="react-scripts" />

declare namespace React {
  function useState<S>(initialState: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  function useEffect(effect: EffectCallback, deps?: DependencyList): void;
  function useCallback<T extends Function>(callback: T, deps: DependencyList): T;
  function useRef<T>(initialValue: T): MutableRefObject<T>;
  function useRef<T>(initialValue: T | null): RefObject<T>;
  function useRef<T = undefined>(): MutableRefObject<T | undefined>;
  
  interface MutableRefObject<T> {
    current: T;
  }
  
  interface RefObject<T> {
    readonly current: T | null;
  }
  
  type Dispatch<A> = (value: A) => void;
  type SetStateAction<S> = S | ((prevState: S) => S);
  type EffectCallback = () => (void | (() => void | undefined));
  type DependencyList = ReadonlyArray<any>;
}

// Browser APIs
declare var localStorage: Storage;
declare var sessionStorage: Storage;
declare var window: Window & typeof globalThis;
declare var document: Document;
declare var navigator: Navigator;
declare var console: Console;
declare var alert: (message?: any) => void;
declare var fetch: typeof globalThis.fetch;
declare var JSON: JSON;
declare var Date: DateConstructor;
declare var Error: ErrorConstructor;
declare var Math: Math;
declare var Number: NumberConstructor;
declare var Array: ArrayConstructor;
declare var Audio: {
  new (src?: string): HTMLAudioElement;
  prototype: HTMLAudioElement;
};
declare var AudioContext: {
  new (contextOptions?: AudioContextOptions): AudioContext;
  prototype: AudioContext;
};
declare var MediaRecorder: {
  new (stream: MediaStream, options?: MediaRecorderOptions): MediaRecorder;
  prototype: MediaRecorder;
};
declare var requestAnimationFrame: (callback: FrameRequestCallback) => number;
declare var cancelAnimationFrame: (handle: number) => void;
declare var Float32Array: Float32ArrayConstructor;
declare var Blob: {
  new (blobParts?: BlobPart[], options?: BlobPropertyBag): Blob;
  prototype: Blob;
};
declare var FormData: {
  new (form?: HTMLFormElement): FormData;
  prototype: FormData;
};

// Extend built-in types
interface Array<T> {
  map<U>(callbackfn: (value: T, index: number, array: T[]) => U, thisArg?: any): U[];
  filter(predicate: (value: T, index: number, array: T[]) => any, thisArg?: any): T[];
  includes(searchElement: T, fromIndex?: number): boolean;
  length: number;
}

interface Number {
  toString(): string;
  toFixed(digits?: number): string;
}

interface Float32Array {
  length: number;
  [index: number]: number;
}

// Event handlers
interface EventTarget {
  value?: string;
  checked?: boolean;
}

interface KeyboardEvent {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
}

interface MediaStream {
  getTracks(): MediaStreamTrack[];
}
