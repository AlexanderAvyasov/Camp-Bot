import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.enableClosingConfirmation();
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<React.StrictMode><App /></React.StrictMode>);
