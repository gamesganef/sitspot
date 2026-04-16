function getLocation(){
  if(navigator.geolocation){
    navigator.geolocation.getCurrentPosition(pos=>{
      alert("Jouw locatie: "+pos.coords.latitude+", "+pos.coords.longitude);
    });
  } else {
    alert("GPS niet beschikbaar");
  }
}

