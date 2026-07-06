import { cn } from '@/lib/utils';

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible');
  });

  it('filters out falsy values', () => {
    expect(cn('a', undefined, null, '', false, 'b')).toBe('a b');
  });

  it('handles Tailwind conflict resolution via twMerge', () => {
    expect(cn('px-4', 'px-6')).toBe('px-6');
  });

  it('accepts array arguments', () => {
    expect(cn(['a', 'b'], 'c')).toBe('a b c');
  });

  it('returns empty string for no inputs', () => {
    expect(cn()).toBe('');
  });
});
