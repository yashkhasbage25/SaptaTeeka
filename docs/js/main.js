$(document).ready(function(){
    $('#toggleNav').click(function(){
      if ($('.navbar').css('left') === '0px') {
        $('.navbar').css('left', '-250px');
        $('.content').css('margin-left', '0px');
      } else {
        $('.navbar').css('left', '0px');
        $('.content').css('margin-left', '250px');
      }
    });
  });