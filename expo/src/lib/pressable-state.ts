import type { PressableStateCallbackType } from 'react-native';

/** React Native Web supplies hovered at runtime; native Pressable only types pressed. */
export function pressableActive(state: PressableStateCallbackType): boolean {
  return state.pressed || ('hovered' in state && state.hovered === true);
}
