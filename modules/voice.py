import streamlit as st
import streamlit.components.v1 as components


def init_voice():
    if "voice_inited" in st.session_state:
        return

    st.markdown("""
    <script>
    window.SymbiontVoice = {
        listening: false,
        speechResult: '',
        onResult: null,

        startListening: function() {
            var self = this;
            var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) { self.speechResult = 'ERR_UNSUPPORTED'; return; }
            if (self.listening) return;
            self.listening = true;
            var r = new SR();
            r.lang = 'cs-CZ';
            r.continuous = false;
            r.interimResults = false;
            r.onresult = function(e) {
                self.speechResult = e.results[0][0].transcript;
                self.listening = false;
                if (self.onResult) self.onResult(self.speechResult);
                var input = document.querySelector('input[data-speech-target]');
                if (input) {
                    var setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    setter.call(input, self.speechResult);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    var form = input.closest('form');
                    if (form) { var btn = form.querySelector('button'); if (btn) btn.click(); }
                }
            };
            r.onerror = function() {
                self.speechResult = 'ERR_FAILED';
                self.listening = false;
            };
            r.start();
        },

        speak: function(text) {
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            var u = new SpeechSynthesisUtterance(text);
            u.lang = 'cs-CZ';
            u.rate = 1.0;
            u.pitch = 0.9;
            window.speechSynthesis.speak(u);
        }
    };
    </script>
    """, unsafe_allow_html=True)
    st.session_state.voice_inited = True


def render_voice_button():
    html = """
    <div style="text-align:center; padding: 0.25rem 0;">
        <button onclick="SymbiontVoice.startListening()" style="
            background: linear-gradient(135deg, #00F2FE22, #22C55E22);
            border: 1px solid #00F2FE44;
            color: #00F2FE;
            width: 48px; height: 48px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.4rem;
            transition: all 0.3s ease;
            font-family: 'JetBrains Mono', monospace;
            display: flex; align-items: center; justify-content: center;
        " onmouseover="this.style.borderColor='#00F2FE88';this.style.boxShadow='0 0 20px #00F2FE33'"
         onmouseout="this.style.borderColor='#00F2FE44';this.style.boxShadow='none'"
         onmousedown="this.style.transform='scale(0.92)'"
         onmouseup="this.style.transform='scale(1)'"
         title="Hlasovy vstup (mluvte cesky)">
            🎤
        </button>
    </div>
    """
    components.html(html, height=72)


def speak(text):
    if not text:
        return
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("<", "").replace(">", "").replace("&", "&amp;")
    js = f"""
    <script>
    (function() {{
        if (window.SymbiontVoice) {{
            setTimeout(function() {{ window.SymbiontVoice.speak('{escaped}'); }}, 200);
        }}
    }})();
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)
