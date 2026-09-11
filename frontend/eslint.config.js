// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*'],
  },
  {
    // These rules flag pre-existing patterns in the NowKart codebase that
    // are valid React patterns and were accepted under SDK 54 / eslint-config-expo 10.
    // They are suppressed here to avoid requiring code restructuring during an SDK upgrade.
    rules: {
      'react-hooks/react-compiler': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/immutability': 'off',
      'react/no-unescaped-entities': 'off',
      'import/no-duplicates': 'warn',
    },
  },
]);
