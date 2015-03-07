var eventsRef = new Firebase('https://thebluealliance.firebaseio.com/events/');
var savedSnapshots = {};

function setActiveEvents(eventKeys) {
  // Remove old eventRefs
  for (eventKey in savedSnapshots) {
    if (!(eventKey in eventKeys)) {
      var eventKey = String(eventKey);
      eventsRef.child(eventKey).off();
      delete savedSnapshots[eventKey];
    }
  }

  // Add new eventRefs
  for (eventKey in eventKeys) {
    var eventKey = String(eventKey)
    if (eventKey in savedSnapshots) {
      updateMatchbar(eventKey, savedSnapshots[eventKey]);
    } else {
      eventsRef.child(eventKey).on('value', function(snapshot) {
        saveSnapshotAndUpdate(snapshot);
      });
    }
  }
}

// Handle matchbar "Follow" settings
var following_set = JSON.parse($.cookie("tba-gameday-following"));
if (following_set == null) {
  following_set = {};
}

function saveSnapshotAndUpdate(snapshot) {
  var eventKey = snapshot.key()
  savedSnapshots[eventKey] = snapshot;
  updateMatchbar(eventKey, snapshot);
}

function updateMatchbar(event_key, snapshot) {
  var data = snapshot.val();
  var event_code = event_key.replace(/[0-9]/g, '').toUpperCase();

  var match_bar = $('.' + event_key + '_matches');

  if (data == null) {
    match_bar.each(function() {
      $(this).html($('<div>', {'class': 'match-number', text: event_code}));
      $(this).append($('<div>', {'class': 'match-bar-info', text: "No matches yet!"}));
    });
    return;
  }

  var matchData = data.matches;

  var matches_list = [];
  for (match_key in matchData) {
    var match = matchData[match_key];
    match.key_name = match_key;
    matches_list.push(match);
  }
  matches_list.sort(function(match1, match2){return match1.order - match2.order});

  var upcoming_matches = [];
  var last_matches = [];
  for (var i=0; i<matches_list.length; i++) {
    var match = matches_list[i];

    if (match.alliances.red.score == -1 || match.alliances.blue.score == -1) {
      upcoming_matches.push(match);
    } else {
      last_matches.push(match);
    }
  }

  match_bar.each(function() { // Because the user might have more than 1 view of a given event open
    var matches = $(this)[0].children;

    if (last_matches != null && last_matches[last_matches.length - 1] != null) {
      var last_match = last_matches[last_matches.length - 1];
      // Remove old matches up to the last played match
      while (matches.length > 0) {
        if (last_match.id == matches[0].id) {
          break;
        }
        matches[0].remove();
      }

      // Render last played match
      var winning_alliance = (last_match.winning_alliance == '') ? 'tie' : last_match.winning_alliance;
      var rendered_match = renderMatch(last_match).addClass('finished_match_' + winning_alliance);
      $(this).prepend(rendered_match);
    }

    if (upcoming_matches != null) {
      for (var i=0; i<upcoming_matches.length; i++) {
        // Render match if not already present in matchbar
        var upcoming_match = upcoming_matches[i];
        if ($(this).children('div[id="' + upcoming_match.key_name + '"').length == 0) {
          var rendered_match = renderMatch(upcoming_match).addClass('upcoming_match');
          // Color followed matches a different color
          var teams = upcoming_match.alliances.red.teams.concat(upcoming_match.alliances.blue.teams);
          for (var n=0; n<teams.length; n++) {
            var number = teams[n].substring(3);
            if (following_set[number]) {
              rendered_match.addClass('followed_match');
              break;
            }
          }
          $(this).append(rendered_match);
        }
      }
    }

    // Add event code to first match
    var match_num = $(this)[0].firstChild.firstChild.innerHTML;
    if (match_num.indexOf(event_code) == -1) {  // Make sure not to add twice
      $(this)[0].firstChild.firstChild.innerHTML = event_code + " " + match_num;
    }
  });
}

function renderMatch(match) {
  var comp_level = match.comp_level.toUpperCase();
  comp_level = (comp_level == 'QM') ? 'Q' : comp_level;
  var match_number = (comp_level == 'QF' || comp_level == 'SF' || comp_level == 'F') ? match.set_number + '-' + match.match_number : match.match_number;
  var match_label = comp_level + match_number;

  var red_teams = match.alliances.red.teams[0].substring(3) + ', ' +
    match.alliances.red.teams[1].substring(3) + ', ' +
    match.alliances.red.teams[2].substring(3);
  var blue_teams = match.alliances.blue.teams[0].substring(3) + ', ' +
    match.alliances.blue.teams[1].substring(3) + ', ' +
    match.alliances.blue.teams[2].substring(3);

  var red_score = match.alliances.red.score;
  var blue_score = match.alliances.blue.score;
  red_score = (red_score == -1) ? '' : ' - ' + red_score;
  blue_score = (blue_score == -1) ? '' : ' - ' + blue_score;

  var match_number = $('<div>', {'class': 'match-number', text: match_label});
  var red_score = $('<div>', {'class': 'red', text: red_teams + red_score});
  var blue_score = $('<div>', {'class': 'blue' , text: blue_teams + blue_score});
  var alliances = $('<div>', {'class': 'alliances'});
  alliances.append(red_score).append(blue_score);

  var new_match = $('<div>', {'class': 'match', 'id': match.key_name}).append(match_number).append(alliances);
  return new_match;
}

$(document).ready(function() {
  // Helper to insert teams in order
  function insertTeam(number) {
    var followed_teams = $("#followed-teams")[0].children;
    var added = false;
    var element = $("<li id=following-" + number + " class='followed-team'>" + number + " <a team-num='" + number + "' class='remove-following' title='Remove'><span class='glyphicon glyphicon-remove'></span></a></li>");
    for (var i=0; i<followed_teams.length; i++) {
      if (parseInt(followed_teams[i].id.replace(/[A-Za-z$-]/g, "")) > number) {
        element.insertBefore($("#" + followed_teams[i].id));
        added = true;
        break;
      }
    }
    if (!added) {
      $("#followed-teams").append(element);
    }

    // Attach deletion callback
    $(".remove-following").click(function() {
      var num = $(this).attr("team-num");
      delete following_set[num];
      $("#following-" + num).remove();
      // Set cookie
      $.cookie("tba-gameday-following", JSON.stringify(following_set));
    });
  }

  // Init
  for (var key in following_set) {
    insertTeam(key);
  }

  // Handle form to follow teams
  $("#follow-form").submit(function() {
    var number = $("#add-team-number").val();
    if (!$.isNumeric(number)) {
     // Reset form
      $("#follow-form")[0].reset();
      return false;
    }

    // Add to list if not already present
    if (!following_set[number]) {
      following_set[number] = true;
      insertTeam(number);
    }

    // Set cookie
    $.cookie("tba-gameday-following", JSON.stringify(following_set));

    // Reset form
    $("#follow-form")[0].reset();
    return false;
  });
});
