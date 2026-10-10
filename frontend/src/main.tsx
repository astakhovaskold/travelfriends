import '@fontsource/bricolage-grotesque/500.css';
import '@fontsource/bricolage-grotesque/700.css';
import '@fontsource/bricolage-grotesque/800.css';
import {render} from 'solid-js/web';
import {App} from './app/App';
import './styles/tailwind.css';
import './styles/design.css';

const root = document.getElementById('root');
if (!root) {
  throw new Error('Missing application root');
}
render(() => <App/>, root);
