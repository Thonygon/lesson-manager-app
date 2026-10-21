/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Animated, Image, Platform, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

const SESSION_KEY = 'classio-intro-seen-v1';
const seenInRuntime = new Set<string>();

const stars = [
  { x: -128, y: -110, color: '#60A5FA', icon: '📚' },
  { x: 125, y: -100, color: '#34D399', icon: '✦' },
  { x: -156, y: 48, color: '#A78BFA', icon: '✎' },
  { x: 154, y: 56, color: '#FBBF24', icon: '◈' },
  { x: -48, y: 145, color: '#38BDF8', icon: '▤' },
  { x: 72, y: 140, color: '#FB7185', icon: '✧' },
] as const;

function hasSeenIntro(sessionKey: string) {
  return seenInRuntime.has(sessionKey);
}

export function IntroConstellation({ ready, tagline, sessionKey = SESSION_KEY, theme = 'dark' }: { ready: boolean; tagline: string; sessionKey?: string; theme?: 'light' | 'dark' }) {
  const { width } = useWindowDimensions();
  const compact = width < 520;
  const web = Platform.OS === 'web';
  const [visible, setVisible] = useState(() => !hasSeenIntro(sessionKey));
  const [minimumElapsed, setMinimumElapsed] = useState(false);
  const [expired, setExpired] = useState(false);
  // Safari can leave React Native Web's animation values at zero while the
  // dashboard is loading. The web artwork must be visible immediately.
  const [arrival] = useState(() => new Animated.Value(Platform.OS === 'web' ? 1 : 0));
  const [reveal] = useState(() => new Animated.Value(Platform.OS === 'web' ? 1 : 0));
  const [exit] = useState(() => new Animated.Value(1));
  const closing = useRef(false);

  useLayoutEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') document.getElementById('classio-boot-overlay')?.remove();
    if (hasSeenIntro(sessionKey)) { seenInRuntime.add(sessionKey); setVisible(false); }
  }, [sessionKey]);

  useEffect(() => {
    if (!visible) return;
    const reducedMotion = Platform.OS === 'web' && typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (!web) Animated.parallel([
      Animated.timing(arrival, { toValue: 1, duration: reducedMotion ? 100 : 1400, useNativeDriver: true }),
      Animated.timing(reveal, { toValue: 1, delay: reducedMotion ? 0 : 500, duration: reducedMotion ? 100 : 850, useNativeDriver: true }),
    ]).start();
    const minimum = setTimeout(() => setMinimumElapsed(true), reducedMotion ? 300 : 2300);
    const deadline = setTimeout(() => setExpired(true), 12000);
    return () => { clearTimeout(minimum); clearTimeout(deadline); if (!web) { arrival.stopAnimation(); reveal.stopAnimation(); } };
  }, [arrival, reveal, visible, web]);

  useEffect(() => {
    if (!visible || !minimumElapsed || (!ready && !expired) || closing.current) return;
    closing.current = true;
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      seenInRuntime.add(sessionKey);
      setVisible(false);
    };
    Animated.timing(exit, { toValue: 0, duration: 520, useNativeDriver: !web }).start(finish);
    // WebKit may not deliver the animation completion callback in a home-screen
    // web app. Always release the overlay after the fade duration.
    if (web) setTimeout(finish, 650);
  }, [exit, expired, minimumElapsed, ready, sessionKey, visible, web]);

  if (!visible) return null;
  const light = theme === 'light';
  const scale = compact ? Math.max(.72, Math.min(1, (width - 28) / 400)) : 1;
  return (
    <Animated.View nativeID="classio-intro-overlay" accessibilityLabel="Classio" style={[styles.overlay, { opacity: exit, backgroundColor: light ? '#F4F8FF' : '#0B1730' }]}>
      <View style={[styles.glowBlue, light && styles.glowBlueLight]} /><View style={[styles.glowGreen, light && styles.glowGreenLight]} />
      <View style={[styles.field, { transform: [{ scale }] }]}>
        {stars.map((star, index) => {
          const distance = Math.hypot(star.x, star.y);
          const angle = Math.atan2(star.y, star.x) * 180 / Math.PI;
          return <View key={`line-${index}`} style={[styles.line, { left: 200 + star.x / 2 - distance / 2, top: 200 + star.y / 2, width: distance, transform: [{ rotate: `${angle}deg` }] }]}><Animated.View style={[styles.lineFill, { backgroundColor: star.color, opacity: arrival, transform: [{ scaleX: arrival }] }]} /></View>;
        })}
        {stars.map((star, index) => <Animated.View nativeID={`classio-intro-star-${index}`} key={`star-${index}`} style={[styles.star, light && styles.starLight, { left: 200 + star.x - 22, top: 200 + star.y - 22, borderColor: star.color, opacity: reveal, transform: [{ translateX: arrival.interpolate({ inputRange: [0, 1], outputRange: [star.x * .32, 0] }) }, { translateY: arrival.interpolate({ inputRange: [0, 1], outputRange: [star.y * .32, 0] }) }, { scale: arrival.interpolate({ inputRange: [0, 1], outputRange: [.55, 1] }) }] }]}><Text style={[styles.starIcon, { color: star.color }]}>{star.icon}</Text></Animated.View>)}
        <Animated.View nativeID="classio-intro-center" style={[styles.center, light && styles.centerLight, { opacity: reveal, transform: [{ scale: reveal.interpolate({ inputRange: [0, 1], outputRange: [.7, 1] }) }] }]}><Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} /></Animated.View>
      </View>
      <Animated.Text style={[styles.tagline, light && styles.taglineLight, { opacity: reveal }]}>{tagline}</Animated.Text>
      <Animated.View style={[styles.progressTrack, light && styles.progressTrackLight, { opacity: reveal }]}><Animated.View style={[styles.progressFill, { transform: [{ scaleX: arrival }] }]} /></Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  overlay: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, zIndex: 1000, backgroundColor: '#0B1730', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  glowBlue: { position: 'absolute', width: 370, height: 370, borderRadius: 185, backgroundColor: '#173669', opacity: .48, top: '14%', left: '-18%' },
  glowGreen: { position: 'absolute', width: 330, height: 330, borderRadius: 165, backgroundColor: '#0B4E49', opacity: .24, bottom: '4%', right: '-15%' },
  glowBlueLight: { backgroundColor: '#B8D5FF', opacity: .62 },
  glowGreenLight: { backgroundColor: '#BAEBDD', opacity: .58 },
  field: { width: 400, height: 400 },
  line: { position: 'absolute', height: 1, overflow: 'hidden' },
  lineFill: { width: '100%', height: 1, opacity: .7 },
  star: { position: 'absolute', width: 44, height: 44, borderRadius: 22, borderWidth: 1, backgroundColor: '#132847', alignItems: 'center', justifyContent: 'center' },
  starLight: { backgroundColor: '#FFFFFF' },
  starIcon: { fontSize: 21, fontWeight: '700' },
  center: { position: 'absolute', left: 110, top: 153, width: 180, height: 94, alignItems: 'center', justifyContent: 'center', backgroundColor: '#102342', borderColor: '#3B82F6', borderWidth: 1, borderRadius: 22, shadowColor: '#60A5FA', shadowOpacity: .65, shadowRadius: 30 },
  centerLight: { backgroundColor: '#FFFFFF', shadowOpacity: .3 },
  logo: { width: 156, height: 64 },
  tagline: { color: '#E2E8F0', fontSize: 15, fontWeight: '700', letterSpacing: .3, textAlign: 'center', marginTop: -12, paddingHorizontal: 24 },
  taglineLight: { color: '#193459' },
  progressTrack: { width: 110, height: 3, borderRadius: 3, backgroundColor: '#274368', marginTop: 24, overflow: 'hidden' },
  progressTrackLight: { backgroundColor: '#CEDDF3' },
  progressFill: { width: '100%', height: 3, borderRadius: 3, backgroundColor: '#60A5FA' },
});
