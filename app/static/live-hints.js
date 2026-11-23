/* Wait 5s AFTER Bibi has finished speaking, not 5s after the server sends audio. */
(function (root) {
  class LiveHintController {
    constructor(onHint, delayMs=5000, schedule=setTimeout, cancel=clearTimeout){
      this.onHint=onHint;this.delayMs=delayMs;this.schedule=schedule;this.cancel=cancel;
      this.timer=null;this.token=0;this.eligible=false;this.heardSpeech=false;this.used=false;
    }
    reset(){
      this.stop();this.eligible=true;this.heardSpeech=false;this.used=false;
    }
    assistantFinished(){
      if(!this.eligible||this.heardSpeech||this.used||this.timer!==null)return;
      const stamp=this.token;
      this.timer=this.schedule(()=>{
        this.timer=null;
        if(stamp!==this.token||!this.eligible||this.heardSpeech||this.used)return;
        this.used=true;this.onHint('timeout');
      },this.delayMs);
    }
    speechDetected(){
      this.heardSpeech=true;
      if(this.timer!==null){this.cancel(this.timer);this.timer=null;}
    }
    manual(){
      if(!this.eligible||this.used)return false;
      if(this.timer!==null){this.cancel(this.timer);this.timer=null;}
      this.used=true;this.onHint('manual');return true;
    }
    stop(){
      ++this.token;
      if(this.timer!==null){this.cancel(this.timer);this.timer=null;}
      this.eligible=false;
    }
  }
  root.BrightSpeakLiveHints=LiveHintController;
})(typeof window==='undefined'?globalThis:window);
