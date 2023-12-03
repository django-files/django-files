$( document ).ready(function() {
    $(".card-body").fadeOut(200);
});

function openNav() {
  document.getElementById("previewSidebar").style.width = "350px";
  document.getElementById("context-placement").style.right = "355px";
  $(".openbtn").hide();
  $(".card-body").fadeIn(300);
}  
function closeNav() {
  document.getElementById("previewSidebar").style.width = "0";
  document.getElementById("context-placement").style.right = "50px";
  $(".openbtn").show();
  $(".card-body").fadeOut(200);
}
