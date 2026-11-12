(() => {
  const savedTheme = localStorage.getItem('brooder-theme');
  if (!document.documentElement.dataset.theme && (savedTheme === 'light' || savedTheme === 'dark')) {
    document.documentElement.dataset.theme = savedTheme;
  }

  const guide = document.getElementById('talkingGuide');
  if (!guide) return;

  const content = {
    landing: [
      { title: 'Welcome to Smart Brooder', text: 'This website is a learning simulator for brooder temperature control. Pip can guide you through the preview and explain what you can try.' },
      { title: 'Explore the brooder preview', text: 'The photo shows chicks inside a brooder, with example temperature readings below. The dashboard adds an animated view driven by your simulation.' },
      { title: 'Try different conditions', text: 'After you create an account, you can change temperatures, heater settings, and weather to see how the model responds.' },
      { title: 'Save and compare your work', text: 'Sign in or create an account to run simulations. Your saved runs are private to your account, and you can return to compare results.' }
    ],
    signup: [
      { title: 'Create your account', text: 'Choose a username and password. Your password is stored securely as a hash, not as readable text.' },
      { title: 'Your simulations stay private', text: 'Runs you save in the dashboard belong to your account and are not shown to other users.' },
      { title: 'Go to the dashboard', text: 'After signing up, start with the recommended values, run a simulation, and explore the results. You can sign in here next time.' }
    ],
    login: [
      { title: 'Sign in to continue', text: 'Enter the username and password you chose when you created your account.' },
      { title: 'Forgot where to start?', text: 'After signing in, use Quick setup. The recommended values are ready for a first simulation, and advanced settings can stay closed.' },
      { title: 'New to Smart Brooder?', text: 'Use the sign-up link to create an account. Your simulation history is private to your account.' }
    ],
    dashboard: [
      { title: 'Start with Quick setup', text: 'The four basic settings are enough for a first run: target temperature, number of chicks, and outdoor day and night temperatures. You can keep the recommended values.' },
      { title: 'What the basic settings mean', text: 'Target temperature is what the controller aims for. The chick count helps estimate heat produced inside the model. Day and night temperatures describe the outside air.' },
      { title: 'Advanced settings are optional', text: 'Brooder details describe insulation and heater capacity. Controller tuning changes how heating responds. Weather timing adds night, rain, or a heater failure. Change one value at a time to see its effect.' },
      { title: 'Run and watch', text: 'Choose Run simulation to see the animated brooder. Use Pause, the timeline slider, and the speed menu to review different moments.' },
      { title: 'Read the chart and results', text: 'The teal line is outdoor temperature. Colored lines show brooder temperature and heater power; the shaded band marks 33 to 37 degrees Celsius. Result cards summarize recovery, temperature differences, and heater capacity.' },
      { title: 'Save and compare runs', text: 'Your simulations appear in Saved runs. Select runs to compare them, choose a run name to load it again, or use Remove to delete it.' }
    ]
  };

  const steps = content[guide.dataset.guide];
  if (!steps) throw new Error(`Unknown talking guide page: ${guide.dataset.guide}`);

  const launch = document.getElementById('guideLaunch');
  const panel = document.getElementById('guidePanel');
  const title = document.getElementById('guideTitle');
  const text = document.getElementById('guideText');
  const counter = document.getElementById('guideCount');
  const progress = document.getElementById('guideProgress');
  const speakButton = document.getElementById('guideSpeak');
  const status = document.getElementById('guideStatus');
  const backButton = document.getElementById('guidePrev');
  const nextButton = document.getElementById('guideNext');
  let stepIndex = 0;

  function stopSpeaking(message = '') {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    guide.classList.remove('is-speaking');
    speakButton.textContent = 'Read aloud';
    status.textContent = message;
  }

  function showStep() {
    stopSpeaking();
    const step = steps[stepIndex];
    title.textContent = step.title;
    text.textContent = step.text;
    counter.textContent = `Step ${stepIndex + 1} of ${steps.length}`;
    progress.style.width = `${((stepIndex + 1) / steps.length) * 100}%`;
    backButton.disabled = stepIndex === 0;
    nextButton.textContent = stepIndex === steps.length - 1 ? 'Close guide' : 'Next';
  }

  function closeGuide() {
    stopSpeaking();
    panel.hidden = true;
    launch.setAttribute('aria-expanded', 'false');
    launch.focus();
  }

  showStep();

  launch.addEventListener('click', () => {
    panel.hidden = false;
    launch.setAttribute('aria-expanded', 'true');
    document.getElementById('guideClose').focus();
  });
  document.getElementById('guideClose').addEventListener('click', closeGuide);
  backButton.addEventListener('click', () => {
    if (stepIndex > 0) {
      stepIndex -= 1;
      showStep();
    }
  });
  nextButton.addEventListener('click', () => {
    if (stepIndex === steps.length - 1) {
      closeGuide();
      return;
    }
    stepIndex += 1;
    showStep();
  });
  speakButton.addEventListener('click', () => {
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      status.textContent = 'Voice narration is not available in this browser. You can read the explanation above.';
      return;
    }
    if (window.speechSynthesis.speaking) {
      stopSpeaking('Narration stopped.');
      return;
    }
    const utterance = new SpeechSynthesisUtterance(`${steps[stepIndex].title}. ${steps[stepIndex].text}`);
    utterance.lang = 'en-US';
    utterance.onstart = () => {
      guide.classList.add('is-speaking');
      speakButton.textContent = 'Stop voice';
      status.textContent = 'Pip is speaking.';
    };
    utterance.onend = () => stopSpeaking('Narration finished.');
    utterance.onerror = event => {
      stopSpeaking(event.error === 'canceled' ? '' : 'Audio could not be played. You can read the explanation above.');
    };
    status.textContent = 'Starting narration…';
    window.speechSynthesis.speak(utterance);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) closeGuide();
  });
  window.addEventListener('pagehide', () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  });
})();
