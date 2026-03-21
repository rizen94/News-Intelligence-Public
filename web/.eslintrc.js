module.exports = {
  extends: [
    'react-app',
    'react-app/jest',
    'eslint:recommended',
    'prettier',
  ],
  rules: {
    // Function declaration preferences
    'prefer-arrow-callback': 'error',
    'prefer-const': 'error',
    'no-var': 'error',
    
    // Console logging — prefer Logger (see web/FRONTEND_STYLE_GUIDE.md); warn only
    'no-console': 'warn',
    'no-debugger': 'warn',
    
    // Variable and function rules
    'no-unused-vars': 'warn',
    'no-undef': 'error',
    'no-unreachable': 'error',
    
    // React specific rules
    'react/function-component-definition': 'off',
    'react/jsx-uses-react': 'off',
    'react/react-in-jsx-scope': 'off',
    
    // Import rules
    'import/order': 'off',

    // Formatting is enforced by Prettier (`npm run format`); avoid conflicting ESLint style rules here.

    // Best practices
    'eqeqeq': 'error',
    'no-eval': 'error',
    'no-implied-eval': 'error',
    'no-new-func': 'error',
    'no-return-assign': 'error',
    'no-sequences': 'error',
    'no-throw-literal': 'error',
    'no-unmodified-loop-condition': 'error',
    'no-useless-call': 'error',
    'no-useless-concat': 'error',
    'no-useless-return': 'error',
    'prefer-promise-reject-errors': 'error',
    'radix': 'warn',
    'yoda': 'error',
    
    // React Hooks rules
    'react-hooks/exhaustive-deps': 'warn'
  },
  env: {
    'browser': true,
    'es6': true,
    'node': true
  },
  parserOptions: {
    'ecmaVersion': 2020,
    'sourceType': 'module',
    'ecmaFeatures': {
      'jsx': true
    }
  },
  settings: {
    'react': {
      'version': 'detect'
    }
  }
};
